import asyncio
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.sse import EventSourceResponse
from pydantic import BaseModel, Field

from app.core import jobs
from app.db.models import Job
from app.formats.base import GenerationConfig
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


class JobRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)
    formats: list[str] = Field(min_length=1)


class UrlJobRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_000)
    formats: list[str] = Field(min_length=1)


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
    steps: list[Step]
    source: SourceDocument
    brief: ContentBrief | None
    outputs: list[FormatResult]  # finished formats only, in registry order
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
        steps=_steps(job),
        source=job.source,
        brief=job.brief,
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
    return _view(jobs.create_job(source, names, GenerationConfig()))


@router.post("/jobs/upload", response_model=JobView, status_code=201)
async def create_job_from_file(
    file: Annotated[UploadFile, File()], formats: Annotated[list[str], Form()]
) -> JobView:
    names = _format_names(formats)
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
    return _create_ingested_job(source, names, "the file")


@router.post("/jobs/url", response_model=JobView, status_code=201)
async def create_job_from_url(req: UrlJobRequest) -> JobView:
    names = _format_names(req.formats)
    try:
        source = await ingest_url(req.url.strip())
    except IngestError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e
    return _create_ingested_job(source, names, "the page")


def _create_ingested_job(source: SourceDocument, names: list[str], what: str) -> JobView:
    """Checks shared by uploads and URLs, which only find out how much text there is after parsing."""
    if not source.blocks:
        raise HTTPException(status_code=422, detail=f"No text found in {what}.")
    if len(source.markdown) > MAX_SOURCE_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"{what.capitalize()} has {len(source.markdown):,} characters of text; "
            f"the limit is {MAX_SOURCE_CHARS:,}.",
        )
    return _view(jobs.create_job(source, names, GenerationConfig()))


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
