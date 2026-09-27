"""Single entry point for model calls.

S0: Gemini only. The semaphore, 429 backoff, dev cache and Ollama fallback
described in CLAUDE.md land when there is more than one call per request (S2).
"""

from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


@lru_cache
def _client() -> genai.Client:
    key = get_settings().gemini_api_key
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key)


async def complete_json(schema: type[T], prompt: str, model: str | None = None) -> T:
    """Fill `schema` from `prompt`. Retries once with the validation error appended."""
    model = model or get_settings().gemini_model
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
    )

    attempt_prompt = prompt
    for attempt in range(2):
        response = await _client().aio.models.generate_content(
            model=model, contents=attempt_prompt, config=config
        )
        try:
            return schema.model_validate_json(response.text or "")
        except ValidationError as e:
            if attempt == 1:
                raise LLMError(f"model output failed validation twice: {e}") from e
            attempt_prompt = (
                f"{prompt}\n\nYour previous response was invalid:\n{e}\n"
                "Return JSON that matches the schema exactly."
            )
    raise AssertionError("unreachable")
