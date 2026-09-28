"""Change one passage of a format's output after generation: edit, accept or regenerate it.

A passage is addressed by its path in the payload (app/verify/grounding.py),
so this works for every format and no format declares anything. Editing or
regenerating writes the new text into the payload, then renders, checks and
saves the format again as the job did, with no model call for that part: the
Markdown, the PDF and the deck all change together.

- Edited text is the reviewer's own. It is marked "edited" and not checked
  against the brief; the reviewer is trusted.
- Regenerating always asks the model, skipping the dev cache. The passage
  it returns is the model's, so it is grounded again, alone.
- Accepting leaves the text and its reasons as they are and marks the flag as
  reviewed. It can be undone.

Revisions run one at a time (one lock, in one process, like the worker). Each
reads the row, works, then replaces only its own format's result, so it never
overwrites another format, even while the job is still running.
"""

import asyncio
import json
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from app.core import jobs
from app.core.llm import complete_json
from app.formats.base import GenerationConfig, OutputAdapter
from app.formats.registry import ADAPTERS
from app.formats.runner import FormatResult, render_format
from app.understand.schemas import ContentBrief
from app.verify.grounding import Passage, field_at, ground, replace_at

_lock = asyncio.Lock()


class ReviseError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status  # HTTP status the API layer should answer with


@dataclass
class _Loaded:
    """A finished format's result, ready to revise one passage of it."""

    brief: ContentBrief
    config: GenerationConfig
    adapter: OutputAdapter
    result: FormatResult
    payload: BaseModel
    passage: Passage


def _load(job_id: str, name: str, path: str) -> _Loaded:
    job = jobs.get_job(job_id)
    if job is None:
        raise ReviseError("No such job.", 404)
    adapter = ADAPTERS.get(name)
    output = job.outputs.get(name)
    if adapter is None or output is None:
        raise ReviseError(f"This job has no {name} output.", 404)
    result = FormatResult.model_validate(output)
    if result.error or result.payload is None:
        raise ReviseError("This format failed; there is nothing to revise.", 409)
    if result.grounding is None:
        raise ReviseError("This output was made before review existed. Generate it again to review it.", 409)
    passage = next((p for p in result.grounding.passages if p.path == path), None)
    if passage is None:
        raise ReviseError(f"No passage at {path}.", 404)
    try:
        payload = adapter.schema.model_validate(result.payload)
    except ValidationError as e:
        raise ReviseError(f"The saved output no longer fits the {name} schema: {e}", 409) from e
    return _Loaded(
        brief=ContentBrief.model_validate(job.brief),
        config=GenerationConfig.model_validate(job.config),
        adapter=adapter,
        result=result,
        payload=payload,
        passage=passage,
    )


def _with_passage(result: FormatResult, passage: Passage, **update) -> FormatResult:
    grounding = result.grounding.model_copy(
        update={"passages": [passage if p.path == passage.path else p for p in result.grounding.passages]}
    )
    return result.model_copy(update={"grounding": grounding, **update})


async def _rewrite(job_id: str, loaded: _Loaded, text: str, passage: Passage) -> FormatResult:
    """Put `text` at the passage's path, then render, check and save the format again."""
    try:
        payload = replace_at(loaded.payload, passage.path, text)
    except ValidationError as e:
        raise ReviseError(f"The new text does not fit this output: {e}", 422) from e
    artifacts, warnings = await render_format(loaded.adapter, payload, loaded.config, loaded.brief)
    result = _with_passage(
        loaded.result, passage, artifacts=artifacts, warnings=warnings, payload=payload.model_dump()
    )
    jobs.save_output(job_id, result)
    return result


async def edit(job_id: str, name: str, path: str, text: str) -> FormatResult:
    async with _lock:
        loaded = _load(job_id, name, path)
        passage = Passage(
            path=path,
            text=text,
            verdict=None,
            items=[],
            blocks=[],
            quote=None,
            new_numbers=[],
            reasons=[],
            review="edited",
        )
        return await _rewrite(job_id, loaded, text, passage)


async def accept(job_id: str, name: str, path: str, accepted: bool) -> FormatResult:
    async with _lock:
        loaded = _load(job_id, name, path)
        passage = loaded.passage
        if accepted and not passage.reasons:
            raise ReviseError("This passage is not flagged; there is nothing to accept.", 409)
        if not accepted and passage.review != "accepted":
            raise ReviseError("This passage has not been accepted.", 409)
        result = _with_passage(
            loaded.result, passage.model_copy(update={"review": "accepted" if accepted else None})
        )
        jobs.save_output(job_id, result)
        return result


class _Rewrite(BaseModel):
    text: str = Field(min_length=1, description="The new text for the one field being rewritten.")


PROMPT = """{format_prompt}

You already wrote this output, as JSON:
{payload}

Rewrite only the field at `{path}`{about}. It currently reads:
{text}
{flag}
Write a replacement that fits where it sits in the output and follows every
rule above. Use only what the brief states. Return only the new text for
that one field.
"""


async def regenerate(job_id: str, name: str, path: str) -> FormatResult:
    """Always asks the model: a reviewer pressing Regenerate wants a new attempt,
    so the dev cache is not read (the answer is still stored)."""
    async with _lock:
        loaded = _load(job_id, name, path)
        adapter = loaded.adapter
        passage = loaded.passage
        description = field_at(adapter.schema, path).description
        prompt = PROMPT.format(
            format_prompt=adapter.prompt(loaded.brief, loaded.config),
            payload=json.dumps(loaded.payload.model_dump(), indent=2, ensure_ascii=False),
            path=path,
            about=f" ({description})" if description else "",
            text=passage.text,
            flag=f"\nIt was flagged for review: {'; '.join(passage.reasons)}. Fix that.\n"
            if passage.reasons
            else "",
        )
        new = await complete_json(_Rewrite, prompt, cached=False)
        text = new.text.strip()
        if not text:
            raise ReviseError("The model returned an empty rewrite. Try again.", 502)

        # Grounded again, alone, against the payload the text will sit in.
        payload = replace_at(loaded.payload, path, text)
        grounding = await ground(payload, loaded.brief, paths={path})
        checked = grounding.passages[0]
        if grounding.error:
            checked.reasons.append(grounding.error)
        return await _rewrite(job_id, loaded, text, checked.model_copy(update={"review": "regenerated"}))
