"""Generate formats from a brief, in parallel. One format failing never loses the others."""

import asyncio
import logging

from pydantic import BaseModel

from app.core.llm import LLMError, complete_json
from app.formats.base import Artifact, GenerationConfig, OutputAdapter
from app.formats.registry import ADAPTERS
from app.understand.schemas import ContentBrief

log = logging.getLogger(__name__)


class FormatResult(BaseModel):
    name: str
    label: str
    artifacts: list[Artifact]
    warnings: list[str]  # from the adapter's check(); never fatal
    payload: dict | None  # what the model filled, before rendering
    error: str | None


async def run_format(adapter: OutputAdapter, brief: ContentBrief, config: GenerationConfig) -> FormatResult:
    try:
        payload = await complete_json(adapter.schema, adapter.prompt(brief, config))
        artifacts = adapter.render(payload, config)
        warnings = adapter.check(payload, artifacts)
    except Exception as e:
        # Anything else is a bug in the adapter, but it still must not take
        # the other formats down with it.
        if not isinstance(e, LLMError):
            log.exception("format %s failed", adapter.name)
        return FormatResult(
            name=adapter.name, label=adapter.label, artifacts=[], warnings=[], payload=None, error=str(e)
        )
    return FormatResult(
        name=adapter.name,
        label=adapter.label,
        artifacts=artifacts,
        warnings=warnings,
        payload=payload.model_dump(),
        error=None,
    )


async def run_formats(names: list[str], brief: ContentBrief, config: GenerationConfig) -> list[FormatResult]:
    """Concurrency is bounded inside complete_json, so every format is started at once."""
    return list(await asyncio.gather(*(run_format(ADAPTERS[n], brief, config) for n in names)))
