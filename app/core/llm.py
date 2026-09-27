"""Single entry point for model calls.

Gemini only for now; the Ollama fallback is deferred (see docs/DECISIONS.md).

- At most `LLM_CONCURRENCY` calls (default 3) are in flight across the
  process. Formats fan out in parallel and the free tier is limited by
  requests per minute.
- Throttling is retried here, with a backoff long enough for a per-minute
  quota to recover. Over quota, the free tier first holds requests until they
  hit the deadline (504 DEADLINE_EXCEEDED), then answers 429. A 504 also
  arrives for single requests when the free tier is short of capacity, and
  that too clears after tens of seconds rather than a few, so both codes get
  the long backoff. A per-day quota is not retried. The SDK retries the other
  transient failures (client timeouts, 408, 500, 502, 503) with its own short
  backoff; dropped connections are retried here like throttling.
- Dev cache: responses that validate are stored under `.cache/llm/`, keyed on
  (model, prompt, schema). On by default; `LLM_CACHE=0` for demo runs.
"""

import asyncio
import hashlib
import json
import logging
import random
import time
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger(__name__)

# A healthy call takes 2-5 s. Free-tier requests occasionally stall for over a
# minute; abandoning them at this point and retrying is far faster than waiting.
REQUEST_TIMEOUT_S = 20

# Waits before each retry when throttled. About 75 s in total, which spans a
# full per-minute quota window. Jitter is added so parallel calls do not retry in step.
THROTTLE_DELAYS_S = (5, 10, 20, 40)
THROTTLE_CODES = {429, 504}

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "llm"


class LLMError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status  # HTTP status the API layer should answer with


@lru_cache
def _client() -> genai.Client:
    key = get_settings().gemini_api_key
    if not key:
        raise LLMError("GEMINI_API_KEY is not set", status=500)
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_S * 1000,  # milliseconds
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=2,
                max_delay=30,
                http_status_codes=[408, 500, 502, 503],  # not 429 or 504: see THROTTLE_CODES
            ),
        ),
    )


@lru_cache
def _slots() -> asyncio.Semaphore:
    return asyncio.Semaphore(get_settings().llm_concurrency)


def _cache_path(model: str, prompt: str, json_schema: dict) -> Path:
    key = json.dumps([model, prompt, json_schema], sort_keys=True)
    return CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()}.json"


async def _generate(model: str, prompt: str, config: types.GenerateContentConfig, label: str) -> str:
    """One model call under the concurrency limit, retrying throttling."""
    for delay in (*THROTTLE_DELAYS_S, None):
        try:
            async with _slots():
                started = time.perf_counter()  # after the wait for a slot
                response = await _client().aio.models.generate_content(
                    model=model, contents=prompt, config=config
                )
        except httpx.TimeoutException as e:
            raise LLMError(
                f"{model} did not respond within {REQUEST_TIMEOUT_S}s, 3 attempts. Try again.",
                status=504,
            ) from e
        except httpx.TransportError as e:
            # A dropped connection (ReadError, RemoteProtocolError...). The SDK
            # only retries timeouts and connect errors, so back off and retry here.
            if delay is None:
                raise LLMError(f"Connection to Gemini failed: {e!r}") from e
            wait = delay + random.uniform(0, delay / 2)
            log.warning("%s %s connection failed (%r), retrying in %.0fs", model, label, e, wait)
            await asyncio.sleep(wait)
            continue
        except genai_errors.APIError as e:
            if e.code not in THROTTLE_CODES:
                raise LLMError(f"Gemini: {e.message}") from e
            if delay is None or "PerDay" in str(e.details):
                raise LLMError(f"Gemini is throttling requests: {e.message}", status=e.code) from e
            wait = delay + random.uniform(0, delay / 2)
            log.warning("%s %s throttled (%d), retrying in %.0fs", model, label, e.code, wait)
            await asyncio.sleep(wait)
            continue

        usage = response.usage_metadata
        log.info(
            "%s %s %.1fs prompt=%s output=%s thinking=%s",
            model,
            label,
            time.perf_counter() - started,
            usage.prompt_token_count if usage else None,
            usage.candidates_token_count if usage else None,
            usage.thoughts_token_count if usage else None,
        )
        return response.text or ""
    raise AssertionError("unreachable")


async def complete_json(schema: type[T], prompt: str, model: str | None = None) -> T:
    """Fill `schema` from `prompt`. Retries once with the validation error appended."""
    settings = get_settings()
    model = model or settings.gemini_model
    json_schema = schema.model_json_schema()

    cache = _cache_path(model, prompt, json_schema) if settings.llm_cache else None
    if cache and cache.exists():
        try:
            result = schema.model_validate_json(cache.read_text())
            log.info("%s %s cache hit", model, schema.__name__)
            return result
        except ValidationError:
            pass  # validators changed under the same JSON schema; regenerate

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=json_schema,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    attempt_prompt = prompt
    for attempt in range(2):
        text = await _generate(model, attempt_prompt, config, f"{schema.__name__} attempt={attempt + 1}")
        try:
            result = schema.model_validate_json(text)
        except ValidationError as e:
            if attempt == 1:
                raise LLMError(f"model output failed validation twice: {e}") from e
            attempt_prompt = (
                f"{prompt}\n\nYour previous response was invalid:\n{e}\n"
                "Return JSON that matches the schema exactly."
            )
            continue
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text)
        return result
    raise AssertionError("unreachable")
