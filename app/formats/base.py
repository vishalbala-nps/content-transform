"""Contract 3 — OutputAdapter. Frozen: see CLAUDE.md before changing.

Every output format is one adapter: a schema the model fills from the
ContentBrief, a prompt, and a renderer that turns the filled payload into
artifacts without calling a model.
"""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, Field

from app.understand.schemas import ContentBrief

Audience = Literal["executive", "technical", "general_public", "media"]
Tone = Literal["formal", "neutral", "conversational", "urgent"]
Language = Literal["en", "hi", "ta", "ml", "kn", "te"]
DetailLevel = Literal["brief", "standard", "detailed"]
Objective = Literal["inform", "warn", "persuade", "instruct", "announce"]
HexColour = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class BrandKit(BaseModel):
    """A copy of a saved brand kit, taken when the job is created, so editing
    the kit later never changes how this job's files re-render."""

    kit_id: str  # the saved kit it was copied from
    org_name: str = Field(max_length=80)  # replaces "Content Transform" in PDF headers and deck footers
    primary: HexColour  # replaces the house accent; code derives the tints
    ink: HexColour = "#1a1f2b"  # body text
    font: str | None = Field(default=None, max_length=60)  # Latin text; the house fonts are the fallback
    logo: str | None = None  # storage key of a PNG or JPEG
    logo_data: bytes | None = Field(default=None, exclude=True)  # loaded by the runner before render(); never saved
    banned_phrases: list[Annotated[str, Field(max_length=100)]] = Field(default=[], max_length=50)


class GenerationConfig(BaseModel):
    """One object threaded to every adapter. Never spread as loose prompt strings."""

    audience: Audience = "general_public"
    tone: Tone = "neutral"
    language: Language = "en"
    detail_level: DetailLevel = "standard"
    objective: Objective = "inform"
    style: str | None = Field(default=None, max_length=300)
    brand_kit: BrandKit | None = None


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

    def check(self, payload: BaseModel, artifacts: list[Artifact], config: GenerationConfig) -> list[str]:
        """Soft warnings, e.g. "tweet 4 is 297/280 characters", including
        targets the config's detail level sets. Empty when clean."""
        ...
