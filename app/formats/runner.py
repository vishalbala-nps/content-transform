"""Generate formats from a brief, in parallel. One format failing never loses the others."""

import asyncio
import logging

from pydantic import BaseModel, Field

from app.core.llm import LLMError, complete_json
from app.core.usage import Usage, metered
from app.formats.base import Artifact, GenerationConfig, OutputAdapter
from app.formats.brand import banned_phrase_warnings, with_logo
from app.formats.brief_view import brief_for_render
from app.formats.registry import ADAPTERS
from app.understand.schemas import ContentBrief
from app.verify.grounding import Grounding, ground

log = logging.getLogger(__name__)


class FormatUsage(BaseModel):
    """What a format's model calls cost. None for a part from before S8b."""

    generate: Usage | None  # writing the payload, validation retry included
    ground: Usage | None  # the grounding check
    revise: Usage = Field(default_factory=Usage)  # regenerated passages since, each re-grounded


class FormatResult(BaseModel):
    name: str
    label: str
    artifacts: list[Artifact]
    warnings: list[str]  # from the adapter's check(); never fatal
    payload: dict | None  # what the model filled, before rendering
    error: str | None
    grounding: Grounding | None = None  # None on failed formats and on jobs from before S7
    usage: FormatUsage | None = None  # None on jobs from before S8b


async def render_format(
    adapter: OutputAdapter, payload: BaseModel, config: GenerationConfig, brief: ContentBrief
) -> tuple[list[Artifact], list[str]]:
    """Artifacts and warnings from a filled payload. No model call: also used after a passage is revised."""
    # Off the event loop: reading the logo, and a PDF or deck takes long
    # enough to stall progress streams.
    config, logo_warnings = await asyncio.to_thread(with_logo, config)
    render_brief = brief_for_render(brief, public=adapter.public)
    artifacts = await asyncio.to_thread(adapter.render, payload, config, render_brief)
    warnings = adapter.check(payload, artifacts, config) + banned_phrase_warnings(payload, config)
    return artifacts, warnings + logo_warnings


async def run_format(adapter: OutputAdapter, brief: ContentBrief, config: GenerationConfig) -> FormatResult:
    # Filled as calls are made, so a format that fails still reports what it spent.
    usage = FormatUsage(generate=Usage(), ground=Usage())
    try:
        with metered(usage.generate):
            payload = await complete_json(adapter.schema, adapter.prompt(brief, config))
        artifacts, warnings = await render_format(adapter, payload, config, brief)
        # Against the full brief: a public format's missing IOCs are policy, not grounding.
        with metered(usage.ground):
            grounding = await ground(payload, brief)
    except Exception as e:
        # Anything else is a bug in the adapter, but it still must not take
        # the other formats down with it.
        if not isinstance(e, LLMError):
            log.exception("format %s failed", adapter.name)
        return FormatResult(
            name=adapter.name,
            label=adapter.label,
            artifacts=[],
            warnings=[],
            payload=None,
            error=str(e),
            usage=usage,
        )
    return FormatResult(
        name=adapter.name,
        label=adapter.label,
        artifacts=artifacts,
        warnings=warnings,
        payload=payload.model_dump(),
        error=None,
        grounding=grounding,
        usage=usage,
    )


async def run_formats(names: list[str], brief: ContentBrief, config: GenerationConfig) -> list[FormatResult]:
    """Concurrency is bounded inside complete_json, so every format is started at once."""
    return list(await asyncio.gather(*(run_format(ADAPTERS[n], brief, config) for n in names)))
