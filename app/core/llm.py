"""Single entry point for model calls.

Gemini only for now. Requests time out and retry with exponential backoff
(timeouts, 429, 5xx) via the SDK's own retry options. The semaphore, dev cache
and Ollama fallback described in CLAUDE.md land with fan-out in S2.
"""

import logging
import time
from functools import lru_cache
from typing import TypeVar

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger(__name__)

# A healthy call takes 2-5 s. Free-tier requests occasionally stall for over a
# minute; abandoning them at this point and retrying is far faster than waiting.
REQUEST_TIMEOUT_S = 20


class LLMError(Exception):
    pass


@lru_cache
def _client() -> genai.Client:
    key = get_settings().gemini_api_key
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_S * 1000,  # milliseconds
            retry_options=types.HttpRetryOptions(attempts=3, initial_delay=2, max_delay=30),
        ),
    )


async def complete_json(schema: type[T], prompt: str, model: str | None = None) -> T:
    """Fill `schema` from `prompt`. Retries once with the validation error appended."""
    model = model or get_settings().gemini_model
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
    )

    attempt_prompt = prompt
    for attempt in range(2):
        started = time.perf_counter()
        try:
            response = await _client().aio.models.generate_content(
                model=model, contents=attempt_prompt, config=config
            )
        except httpx.TimeoutException as e:
            raise LLMError(
                f"{model} did not respond within {REQUEST_TIMEOUT_S}s, 3 attempts. Try again."
            ) from e
        usage = response.usage_metadata
        log.info(
            "%s %s attempt=%d %.1fs prompt=%s output=%s thinking=%s",
            model,
            schema.__name__,
            attempt + 1,
            time.perf_counter() - started,
            usage.prompt_token_count if usage else None,
            usage.candidates_token_count if usage else None,
            usage.thoughts_token_count if usage else None,
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
