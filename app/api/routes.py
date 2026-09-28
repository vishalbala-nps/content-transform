import asyncio
from collections.abc import AsyncIterable, Awaitable
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core import brand_kits, jobs, revise, storage
from app.core.brand_kits import BrandKitError, BrandKitFields
from app.core.llm import LLMError
from app.core.usage import Usage
from app.db.models import Job
from app.formats.base import Artifact, Audience, BrandKit, DetailLevel, GenerationConfig, Objective, Tone
from app.formats.registry import ADAPTERS
from app.formats.runner import FormatResult
from app.ingest.base import SourceDocument
from app.ingest.common import MAX_FILE_BYTES, IngestError
from app.ingest.registry import INGESTERS, ingest_file
from app.ingest.text import ingest_text
from app.ingest.url import ingest_url
from app.understand.schemas import ContentBrief

router = APIRouter(prefix="/api")

# How often the event stream checks the job row for changes.
POLL_S = 0.5

# Longest source accepted, pasted or extracted from a file or a page.
MAX_SOURCE_CHARS = 100_000


class FormatInfo(BaseModel):
    name: str
    label: str


class JobSettings(BaseModel):
    """What a job request chooses; the job's GenerationConfig is built from it.
    Language is added when translation exists."""

    model_config = ConfigDict(extra="forbid")

    audience: Audience = "general_public"
    tone: Tone = "neutral"
    detail_level: DetailLevel = "standard"
    objective: Objective = "inform"
    style: str | None = Field(default=None, max_length=300)
    brand_kit_id: str | None = None  # a saved kit; the job keeps a copy of it

    def to_config(self) -> GenerationConfig:
        kit = None
        if self.brand_kit_id:
            kit = brand_kits.get_kit(self.brand_kit_id)
            if kit is None:
                raise HTTPException(status_code=422, detail="That brand kit no longer exists.")
        style = (self.style or "").strip() or None
        return GenerationConfig(
            **self.model_dump(exclude={"style", "brand_kit_id"}), style=style, brand_kit=kit
        )


class JobRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)
    formats: list[str] = Field(min_length=1)
    settings: JobSettings = JobSettings()


class UrlJobRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_000)
    formats: list[str] = Field(min_length=1)
    settings: JobSettings = JobSettings()


class Step(BaseModel):
    name: str  # "brief" or a format name
    label: str
    status: Literal["pending", "running", "done", "failed", "skipped"]


class JobView(BaseModel):
    id: str
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime
    updated_at: datetime
    formats: list[str]  # requested, in registry order
    config: GenerationConfig
    steps: list[Step]
    source: SourceDocument
    brief: ContentBrief | None
    brief_usage: Usage | None  # the brief's model calls; None on jobs from before S8b
    outputs: list[FormatResult]  # finished formats only, in registry order; each has its own usage
    error: str | None  # why the whole job failed; a format's own error is on its output


class JobSummary(BaseModel):
    id: str
    status: str
    created_at: datetime
    title: str
    formats: list[str]


def _utc(dt: datetime) -> datetime:
    # SQLite hands back naive datetimes; they were stored as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _label(name: str) -> str:
    adapter = ADAPTERS.get(name)
    return adapter.label if adapter else name


def _steps(job: Job) -> list[Step]:
    """Progress, derived from what the row already holds rather than stored beside it."""
    active = job.status == "running"
    if job.brief:
        brief_status = "done"
    elif job.status == "failed":
        brief_status = "failed"
    else:
        brief_status = "running" if active else "pending"
    steps = [Step(name="brief", label="Content brief", status=brief_status)]
    for name in job.formats:
        output = job.outputs.get(name)
        if output:
            status = "failed" if output["error"] else "done"
        elif job.status == "failed":
            status = "skipped"
        else:
            status = "running" if active and job.brief else "pending"
        steps.append(Step(name=name, label=_label(name), status=status))
    return steps


def _view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        status=job.status,
        created_at=_utc(job.created_at),
        updated_at=_utc(job.updated_at),
        formats=job.formats,
        config=job.config,
        steps=_steps(job),
        source=job.source,
        brief=job.brief,
        brief_usage=job.brief_usage,
        outputs=[job.outputs[n] for n in job.formats if n in job.outputs],
        error=job.error,
    )


def _title(job: Job) -> str:
    if job.brief:
        return job.brief["title"]
    source = SourceDocument.model_validate(job.source)
    first = source.meta.get("title") or (source.blocks[0].text if source.blocks else "")
    return first if len(first) <= 80 else first[:79] + "…"


def _load_job(job_id: str) -> Job:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such job.")
    return job


@router.get("/formats", response_model=list[FormatInfo])
async def formats() -> list[FormatInfo]:
    return [FormatInfo(name=a.name, label=a.label) for a in ADAPTERS.values()]


@router.get("/source-types", response_model=list[str])
async def source_types() -> list[str]:
    """File extensions an upload may have, e.g. ".docx"."""
    return list(INGESTERS)


def _format_names(requested: list[str]) -> list[str]:
    if not requested:
        raise HTTPException(status_code=422, detail="Choose at least one format.")
    unknown = [f for f in requested if f not in ADAPTERS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown format: {', '.join(unknown)}")
    # Registry order, not request order, so the UI always lists outputs the same way.
    return [n for n in ADAPTERS if n in requested]


@router.post("/jobs", response_model=JobView, status_code=201)
async def create_job(req: JobRequest) -> JobView:
    names = _format_names(req.formats)
    source = ingest_text(req.text)
    if not source.blocks:
        raise HTTPException(status_code=422, detail="Source text is empty.")
    return _view(jobs.create_job(source, names, req.settings.to_config()))


@router.post("/jobs/upload", response_model=JobView, status_code=201)
async def create_job_from_file(
    file: Annotated[UploadFile, File()],
    formats: Annotated[list[str], Form()],
    settings: Annotated[str | None, Form(description="JobSettings as JSON")] = None,
) -> JobView:
    names = _format_names(formats)
    try:
        config = JobSettings.model_validate_json(settings or "{}").to_config()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Invalid settings: {e}") from e
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Files over {MAX_FILE_BYTES // 2**20} MB are not accepted."
        )
    try:
        # Parsing is CPU-bound; off the event loop so progress streams keep flowing.
        source = await asyncio.to_thread(ingest_file, file.filename or "", data)
    except IngestError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return _create_ingested_job(source, names, config, "the file")


@router.post("/jobs/url", response_model=JobView, status_code=201)
async def create_job_from_url(req: UrlJobRequest) -> JobView:
    names = _format_names(req.formats)
    try:
        source = await ingest_url(req.url.strip())
    except IngestError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return _create_ingested_job(source, names, req.settings.to_config(), "the page")


def _create_ingested_job(
    source: SourceDocument, names: list[str], config: GenerationConfig, what: str
) -> JobView:
    """Checks shared by uploads and URLs, which only find out how much text there is after parsing."""
    if not source.blocks:
        raise HTTPException(status_code=422, detail=f"No text found in {what}.")
    if len(source.markdown) > MAX_SOURCE_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"{what.capitalize()} has {len(source.markdown):,} characters of text; "
            f"the limit is {MAX_SOURCE_CHARS:,}.",
        )
    return _view(jobs.create_job(source, names, config))


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs() -> list[JobSummary]:
    return [
        JobSummary(
            id=j.id, status=j.status, created_at=_utc(j.created_at), title=_title(j), formats=j.formats
        )
        for j in jobs.list_jobs()
    ]


@router.get("/jobs/{job_id}", response_model=JobView)
async def get_job(job: Annotated[Job, Depends(_load_job)]) -> JobView:
    return _view(job)


@router.get("/jobs/{job_id}/files/{format_name}/{filename}")
async def download_artifact(
    job: Annotated[Job, Depends(_load_job)], format_name: str, filename: str
) -> Response:
    """One artifact as a download: text from the job row, binaries from storage.

    Looked up on the row rather than built into a storage path, so only files
    the job actually produced can be fetched.
    """
    output = job.outputs.get(format_name)
    artifact = next(
        (Artifact.model_validate(a) for a in (output or {}).get("artifacts", []) if a["filename"] == filename),
        None,
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="No such file in this job.")
    if artifact.path:
        try:
            content = await asyncio.to_thread(storage.read, artifact.path)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail="The file for this artifact is missing.") from e
        media_type = artifact.media_type
    else:
        content = (artifact.text or "").encode()
        media_type = f"{artifact.media_type}; charset=utf-8"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


class PassageEdit(BaseModel):
    path: str
    text: str = Field(min_length=1, max_length=10_000)


class PassageAccept(BaseModel):
    path: str
    accepted: bool = True  # false undoes an earlier accept


class PassageRegenerate(BaseModel):
    path: str


class PassageDelete(BaseModel):
    path: str


async def _revise(call: Awaitable[FormatResult]) -> FormatResult:
    """Each revision returns the format's new result; the job row already holds it."""
    try:
        return await call
    except (revise.ReviseError, LLMError) as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e


@router.post("/jobs/{job_id}/outputs/{format_name}/edit", response_model=FormatResult)
async def edit_passage(job_id: str, format_name: str, req: PassageEdit) -> FormatResult:
    """Replace a passage with the reviewer's text. Trusted: not checked against the brief."""
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="The new text is empty.")
    return await _revise(revise.edit(job_id, format_name, req.path, req.text.strip()))


@router.post("/jobs/{job_id}/outputs/{format_name}/accept", response_model=FormatResult)
async def accept_passage(job_id: str, format_name: str, req: PassageAccept) -> FormatResult:
    return await _revise(revise.accept(job_id, format_name, req.path, req.accepted))


@router.post("/jobs/{job_id}/outputs/{format_name}/regenerate", response_model=FormatResult)
async def regenerate_passage(job_id: str, format_name: str, req: PassageRegenerate) -> FormatResult:
    """Always asks the model, never the dev cache. Waits for it: seconds on
    Gemini, up to a minute or so on Ollama."""
    return await _revise(revise.regenerate(job_id, format_name, req.path))


@router.post("/jobs/{job_id}/outputs/{format_name}/delete", response_model=FormatResult)
async def delete_passage(job_id: str, format_name: str, req: PassageDelete) -> FormatResult:
    """Remove the list entry holding the passage (a paragraph, a tweet, a whole
    slide). Fields outside any list are required: 409."""
    return await _revise(revise.delete(job_id, format_name, req.path))


@router.get("/jobs/{job_id}/events", response_class=EventSourceResponse)
async def job_events(job: Annotated[Job, Depends(_load_job)]) -> AsyncIterable[JobView]:
    """The job's full state now, then again after every change, until it finishes.

    Reads the jobs table, never the worker, so any number of tabs can watch a
    job and one opened after a restart sees the same thing.
    """
    seen = None
    while True:
        updated_at = jobs.job_updated_at(job.id)
        if updated_at != seen:
            seen = updated_at
            job = jobs.get_job(job.id)
            yield _view(job)
            if job.status in jobs.FINISHED:
                return
        await asyncio.sleep(POLL_S)


# --- Brand kits ---------------------------------------------------------------


def _kit_call(call, *args):
    try:
        return call(*args)
    except BrandKitError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e


@router.get("/brand-kits", response_model=list[BrandKit])
async def list_brand_kits() -> list[BrandKit]:
    return brand_kits.list_kits()


@router.post("/brand-kits", response_model=BrandKit, status_code=201)
async def create_brand_kit(fields: BrandKitFields) -> BrandKit:
    return brand_kits.create_kit(fields)


@router.put("/brand-kits/{kit_id}", response_model=BrandKit)
async def update_brand_kit(kit_id: str, fields: BrandKitFields) -> BrandKit:
    """Changes the saved kit only; jobs already made with it keep their copy."""
    return _kit_call(brand_kits.update_kit, kit_id, fields)


@router.delete("/brand-kits/{kit_id}", status_code=204)
async def delete_brand_kit(kit_id: str) -> Response:
    _kit_call(brand_kits.delete_kit, kit_id)
    return Response(status_code=204)


@router.put("/brand-kits/{kit_id}/logo", response_model=BrandKit)
async def upload_brand_kit_logo(kit_id: str, file: Annotated[UploadFile, File()]) -> BrandKit:
    """A PNG or JPEG, checked by its content, not its name."""
    data = await file.read(brand_kits.MAX_LOGO_BYTES + 1)
    return await asyncio.to_thread(_kit_call, brand_kits.set_logo, kit_id, data)


@router.delete("/brand-kits/{kit_id}/logo", response_model=BrandKit)
async def remove_brand_kit_logo(kit_id: str) -> BrandKit:
    return _kit_call(brand_kits.remove_logo, kit_id)


@router.get("/brand-kits/{kit_id}/logo")
async def brand_kit_logo(kit_id: str) -> Response:
    """The kit's current logo, for the UI to show."""
    kit = brand_kits.get_kit(kit_id)
    if kit is None or kit.logo is None:
        raise HTTPException(status_code=404, detail="This brand kit has no logo.")
    try:
        data = await asyncio.to_thread(storage.read, kit.logo)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="The logo file is missing.") from e
    media_type = "image/png" if kit.logo.endswith(".png") else "image/jpeg"
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "no-cache"})
