import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    llm_concurrency: int  # model calls in flight at once, across all jobs
    llm_cache: bool  # dev cache under .cache/llm/; set LLM_CACHE=0 for demo runs


def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        llm_concurrency=int(os.environ.get("LLM_CONCURRENCY", "3")),
        llm_cache=os.environ.get("LLM_CACHE", "1") != "0",
    )
