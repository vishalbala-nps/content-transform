import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_DATABASE_URL = f"sqlite:///{Path(__file__).resolve().parents[2] / 'storage' / 'app.db'}"

PROVIDERS = ("gemini", "ollama")


@dataclass(frozen=True)
class Settings:
    llm_provider: Literal["gemini", "ollama"]  # which one every model call goes to
    gemini_api_key: str | None
    gemini_model: str
    gemini_strong_model: str  # for the few calls worth more: retrying a translation that went wrong
    ollama_url: str
    ollama_model: str
    ollama_num_ctx: int  # context window in tokens; Ollama's own default (4096) cuts long sources
    ollama_timeout_s: float  # local models are slow: a brief can take minutes on a laptop
    llm_concurrency: int  # model calls in flight at once, across all jobs
    llm_cache: bool  # dev cache under .cache/llm/; set LLM_CACHE=0 for demo runs
    llm_cache_delay_s: float  # dev only: each cache hit waits this long, like a real call
    database_url: str  # SQLite in dev; the models are Postgres-compatible
    session_hours: float  # how long a sign-in lasts, from signing in
    session_cookie_secure: bool  # send the session cookie over HTTPS only; set SESSION_COOKIE_SECURE=1 when served over HTTPS
    allow_private_urls: bool  # let link sources reach private and loopback addresses (an intranet); off by default
    allowed_origins: tuple[str, ...]  # the site's public origin(s), when a proxy in front rewrites Host

    @property
    def llm_model(self) -> str:
        return self.ollama_model if self.llm_provider == "ollama" else self.gemini_model

    @property
    def llm_strong_model(self) -> str:
        """Ollama has one local model, so it is the strong one too."""
        return self.ollama_model if self.llm_provider == "ollama" else self.gemini_strong_model


def get_settings() -> Settings:
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}, not {provider!r}")
    return Settings(
        llm_provider=provider,
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        gemini_strong_model=os.environ.get("GEMINI_STRONG_MODEL", "gemini-3.5-flash"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen3:latest"),
        ollama_num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "16384")),
        ollama_timeout_s=float(os.environ.get("OLLAMA_TIMEOUT_S", "600")),
        llm_concurrency=int(os.environ.get("LLM_CONCURRENCY", "3")),
        llm_cache=os.environ.get("LLM_CACHE", "1") != "0",
        llm_cache_delay_s=float(os.environ.get("LLM_CACHE_DELAY_S", "0")),
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        session_hours=float(os.environ.get("SESSION_HOURS", "8")),
        session_cookie_secure=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
        allow_private_urls=os.environ.get("ALLOW_PRIVATE_URLS", "0") == "1",
        allowed_origins=tuple(
            o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
        ),
    )
