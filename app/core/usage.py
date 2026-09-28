"""Tokens and cost of model calls, summed for whatever asked for them.

`complete_json` (app/core/llm.py) records every call it makes. Code that
wants to know what a step cost wraps it in `metered()`:

    with metered() as usage:
        brief = await build_brief(doc)

Every call made inside the block counts, including calls in tasks the block
starts (asyncio copies the context into them). Blocks nest: an outer meter
counts the calls of the inner ones too. Nothing outside llm.py knows about
tokens.

Cost is worked out per call, from PRICES as they are when the call is made,
so changing a price later never rewrites what an old job cost.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class Price:
    """US dollars per million tokens."""

    input: float
    cached_input: float  # input the provider served from its own context cache
    output: float  # includes thinking tokens, which are billed as output


# Gemini API, paid tier, Standard, text input. Source:
# https://ai.google.dev/gemini-api/docs/pricing (page updated 2026-09-24).
# A Gemini model missing here is counted as unpriced, not as free.
GEMINI_PRICES = {
    "gemini-3.5-flash-lite": Price(input=0.30, cached_input=0.03, output=2.50),
    "gemini-3.5-flash": Price(input=1.50, cached_input=0.15, output=9.00),
}
# Ollama runs locally: its calls are priced at zero.
FREE = Price(input=0, cached_input=0, output=0)


class Usage(BaseModel):
    calls: int = 0  # answered by the provider; a validation retry is a second call
    cached_calls: int = 0  # answered from the dev cache: no tokens, no cost
    input_tokens: int = 0
    cached_input_tokens: int = 0  # the part of input_tokens billed at the cached rate
    output_tokens: int = 0  # thinking included
    cost_usd: float = 0.0
    unpriced_calls: int = 0  # calls to a model with no price above; cost_usd leaves them out

    def add(self, other: "Usage") -> None:
        for name in type(self).model_fields:
            setattr(self, name, getattr(self, name) + getattr(other, name))


def total(*parts: Usage | None) -> Usage:
    """The sum of the parts that exist."""
    result = Usage()
    for part in parts:
        if part is not None:
            result.add(part)
    return result


_meters: ContextVar[tuple[Usage, ...]] = ContextVar("usage_meters", default=())


@contextmanager
def metered(usage: Usage | None = None) -> Iterator[Usage]:
    """Count the model calls made inside the block into `usage` (a new one if not given)."""
    usage = usage if usage is not None else Usage()
    token = _meters.set((*_meters.get(), usage))
    try:
        yield usage
    finally:
        _meters.reset(token)


def _price(provider: str, model: str) -> Price | None:
    return FREE if provider == "ollama" else GEMINI_PRICES.get(model)


def record_call(provider: str, model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> None:
    """One call the provider answered. Called by llm.py only."""
    price = _price(provider, model)
    call = Usage(
        calls=1,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        unpriced_calls=0 if price else 1,
    )
    if price:
        call.cost_usd = (
            (input_tokens - cached_input_tokens) * price.input
            + cached_input_tokens * price.cached_input
            + output_tokens * price.output
        ) / 1_000_000
    for meter in _meters.get():
        meter.add(call)


def record_cached() -> None:
    """One call answered from the dev cache. Called by llm.py only."""
    for meter in _meters.get():
        meter.cached_calls += 1
