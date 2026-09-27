"""Contract 3 — OutputAdapter. Frozen: see CLAUDE.md before changing.

Every output format is one adapter: a schema the model fills from the
ContentBrief, a prompt, and a renderer that turns the filled payload into
artifacts without calling a model.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.understand.schemas import ContentBrief


class GenerationConfig(BaseModel):
    """One object threaded to every adapter. Never spread as loose prompt strings."""

    audience: Literal["executive", "technical", "general_public", "media"] = "general_public"
    tone: Literal["formal", "neutral", "conversational", "urgent"] = "neutral"
    language: str = "en"
    detail_level: Literal["brief", "standard", "detailed"] = "standard"
    objective: Literal["inform", "warn", "persuade", "instruct", "announce"] = "inform"
    style: str | None = None
    # brand_kit: BrandKit | None arrives with S8.


class Artifact(BaseModel):
    """A text artifact carries `text`; a binary one (PDF, PPTX) carries `data`.

    `render()` fills `data` and does no I/O. The job saves the bytes to storage
    and records where in `path`; `data` itself is never serialised.
    """

    filename: str  # "linkedin.md", "exec_summary.pdf"
    media_type: str  # "text/markdown", "application/pdf"
    text: str | None = None  # the full text: what Copy uses
    parts: list[str] = []  # separately postable pieces, e.g. each tweet in a thread
    part_limit: int | None = None  # character limit per part, shown against each count
    data: bytes | None = Field(default=None, exclude=True)  # binary content, straight from render()
    path: str | None = None  # storage key of the saved bytes


class OutputAdapter(Protocol):
    name: str  # registry key and API id: "linkedin"
    label: str  # UI label: "LinkedIn post"
    public: bool  # public-facing: the IOC policy applies
    schema: type[BaseModel]  # what the model fills

    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str: ...

    def render(self, payload: BaseModel, config: GenerationConfig, brief: ContentBrief) -> list[Artifact]:
        """Lay out the payload. Exact values (versions, CVE ids, hashes) are
        copied from `brief`, never retyped by the model. A public format gets
        the brief without IOCs, as its prompt does (see brief_view.py)."""
        ...

    def check(self, payload: BaseModel, artifacts: list[Artifact]) -> list[str]:
        """Soft warnings, e.g. "tweet 4 is 297/280 characters". Empty when clean."""
        ...
