"""Generate formats from a brief, in parallel. One format failing never loses the others."""

import asyncio
import logging

from pydantic import BaseModel

from app.core.llm import LLMError, complete_json
from app.formats.base import Artifact, GenerationConfig, OutputAdapter
from app.formats.brief_view import brief_for_render
from app.formats.registry import ADAPTERS
from app.understand.schemas import ContentBrief
from app.verify.grounding import Grounding, ground

log = logging.getLogger(__name__)


class FormatResult(BaseModel):
    name: str
    label: str
    artifacts: list[Artifact]
    warnings: list[str]  # from the adapter's check(); never fatal
    payload: dict | None  # what the model filled, before rendering
    error: str | None
    grounding: Grounding | None = None  # None on failed formats and on jobs from before S7


async def run_format(adapter: OutputAdapter, brief: ContentBrief, config: GenerationConfig) -> FormatResult:
    try:
        payload = await complete_json(adapter.schema, adapter.prompt(brief, config))
        # Off the event loop: a PDF or deck takes long enough to stall progress streams.
        render_brief = brief_for_render(brief, public=adapter.public)
        artifacts = await asyncio.to_thread(adapter.render, payload, config, render_brief)
        warnings = adapter.check(payload, artifacts)
        # Against the full brief: a public format's missing IOCs are policy, not grounding.
        grounding = await ground(payload, brief)
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
        grounding=grounding,
    )


async def run_formats(names: list[str], brief: ContentBrief, config: GenerationConfig) -> list[FormatResult]:
    """Concurrency is bounded inside complete_json, so every format is started at once."""
    return list(await asyncio.gather(*(run_format(ADAPTERS[n], brief, config) for n in names)))
