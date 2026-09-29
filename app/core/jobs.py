"""Generation runs as a job in the background; its progress lives in the jobs table.

Creating a job stores the ingested source as a queued row. One worker task in
this process runs queued jobs oldest first, writing the brief and then each
format's result to the row as soon as it exists. Everything else (the API, the
SSE stream) only reads the row, so closing the tab loses nothing, and a job
cut off by a restart is queued again and resumes after its last saved step.

- One job at a time. Model calls are limited process-wide (LLM_CONCURRENCY),
  so jobs running side by side would only share the same slots.
- One server process. A second process would run the same jobs.
- Database calls are synchronous, on the event loop: single-row SQLite reads
  and writes of about a millisecond. With no await between reading a row and
  writing it back, parallel formats cannot overwrite each other's results.
"""

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy import select, update

from app.core import storage
from app.core.llm import LLMError
from app.core.usage import Usage, metered
from app.db.models import Job, session
from app.formats.base import GenerationConfig
from app.formats.registry import ADAPTERS
from app.formats.runner import FormatResult, run_format
from app.formats.translate import translate_brief
from app.ingest.base import SourceDocument
from app.understand.brief import build_brief
from app.understand.schemas import ContentBrief

log = logging.getLogger(__name__)

FINISHED = ("done", "failed")

NO_CLAIMS = (
    "No claims could be drawn from the source, so no format was written. "
    "Check that the source has readable text; a small model may also return none."
)

_wake = asyncio.Event()  # set when a job is queued


def create_job(source: SourceDocument, formats: list[str], config: GenerationConfig) -> Job:
    job = Job(
        id=uuid.uuid4().hex,
        status="queued",
        formats=formats,
        config=config.model_dump(mode="json"),
        source=source.model_dump(mode="json"),
        brief=None,
        brief_usage=None,
        brief_translation=None,
        outputs={},
        error=None,
    )
    with session() as s:
        s.add(job)
        s.commit()
    _wake.set()
    return job


def get_job(job_id: str) -> Job | None:
    with session() as s:
        return s.get(Job, job_id)


def job_updated_at(job_id: str) -> datetime | None:
    """Cheap change check for the SSE stream: one column, not the whole row."""
    with session() as s:
        return s.scalar(select(Job.updated_at).where(Job.id == job_id))


def list_jobs(limit: int = 50) -> list[Job]:
    with session() as s:
        return list(s.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)))


def requeue_interrupted() -> int:
    """Queue again any job left running by a previous process. Call before the worker starts."""
    with session() as s:
        count = s.execute(update(Job).where(Job.status == "running").values(status="queued")).rowcount
        s.commit()
    if count:
        log.info("requeued %d interrupted job(s)", count)
    return count


def _update(job_id: str, **fields) -> None:
    with session() as s:
        job = s.get(Job, job_id)
        for key, value in fields.items():
            setattr(job, key, value)
        s.commit()


def _next_queued() -> str | None:
    with session() as s:
        return s.scalar(
            select(Job.id).where(Job.status == "queued").order_by(Job.created_at).limit(1)
        )


def save_output(job_id: str, result: FormatResult) -> None:
    """Files first, then the row: a result on the row always has its files.
    Replaces any earlier result for the format, files included."""
    for artifact in result.artifacts:
        if artifact.data is not None:
            artifact.path = f"{job_id}/{result.name}/{artifact.filename}"
            storage.save(artifact.path, artifact.data)
    with session() as s:
        job = s.get(Job, job_id)
        job.outputs = {**job.outputs, result.name: result.model_dump(mode="json")}
        s.commit()


async def _run_and_save(
    job_id: str, name: str, brief: ContentBrief, config: GenerationConfig, brief_translation: dict | None
) -> None:
    result = await run_format(ADAPTERS[name], brief, config, brief_translation)  # never raises
    save_output(job_id, result)


async def run_job(job_id: str) -> None:
    _update(job_id, status="running")
    job = get_job(job_id)
    config = GenerationConfig.model_validate(job.config)
    try:
        if job.brief is None:
            # Added to an attempt a restart cut short, if any.
            usage = Usage.model_validate(job.brief_usage) if job.brief_usage else Usage()
            with metered(usage):
                try:
                    brief = await build_brief(SourceDocument.model_validate(job.source))
                finally:
                    # Saved even when the brief fails or is cut short: its calls were still billed.
                    _update(job_id, brief_usage=usage.model_dump())
            _update(job_id, brief=brief.model_dump(mode="json"))
        else:
            brief = ContentBrief.model_validate(job.brief)  # resuming after a restart
        if not brief.claims:
            # Formats would be written from nothing, and grounding would have nothing to check.
            _update(job_id, status="failed", error=NO_CLAIMS)
            return
        brief_translation = job.brief_translation
        if config.language != "en" and brief_translation is None:
            # Once per job, before the formats that copy this wording into files.
            usage = Usage.model_validate(get_job(job_id).brief_usage or {})
            with metered(usage):
                try:
                    brief_translation = await translate_brief(brief, config.language)
                finally:
                    _update(job_id, brief_usage=usage.model_dump())
            _update(job_id, brief_translation=brief_translation)
        todo = [n for n in job.formats if n not in job.outputs]
        await asyncio.gather(*(_run_and_save(job_id, n, brief, config, brief_translation) for n in todo))
    except LLMError as e:
        _update(job_id, status="failed", error=str(e))
        return
    except Exception as e:
        log.exception("job %s failed", job_id)
        _update(job_id, status="failed", error=f"Internal error: {e!r}")
        return
    _update(job_id, status="done")


async def worker() -> None:
    """Run queued jobs until cancelled. A job cancelled mid-run stays `running`
    in the table, and `requeue_interrupted` picks it up on the next start."""
    while True:
        _wake.clear()
        job_id = _next_queued()
        if job_id is None:
            await _wake.wait()
            continue
        log.info("job %s started", job_id)
        try:
            await run_job(job_id)
        except Exception:
            # Only reachable if the database itself failed. Do not spin on it.
            log.exception("job %s could not be run", job_id)
            await asyncio.sleep(5)
            continue
        log.info("job %s %s", job_id, get_job(job_id).status)
