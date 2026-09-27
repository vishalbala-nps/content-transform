import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATABASE_URL = f"sqlite:///{Path(__file__).resolve().parents[2] / 'storage' / 'app.db'}"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    llm_concurrency: int  # model calls in flight at once, across all jobs
    llm_cache: bool  # dev cache under .cache/llm/; set LLM_CACHE=0 for demo runs
    llm_cache_delay_s: float  # dev only: each cache hit waits this long, like a real call
    database_url: str  # SQLite in dev; the models are Postgres-compatible


def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        llm_concurrency=int(os.environ.get("LLM_CONCURRENCY", "3")),
        llm_cache=os.environ.get("LLM_CACHE", "1") != "0",
        llm_cache_delay_s=float(os.environ.get("LLM_CACHE_DELAY_S", "0")),
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
