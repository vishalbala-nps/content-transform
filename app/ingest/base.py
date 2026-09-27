"""Contract 1 — SourceDocument. Frozen: see CLAUDE.md before changing.

Produced by every ingester. Downstream code never knows the input type.
"""

from typing import Literal

from pydantic import BaseModel


class Block(BaseModel):
    id: str  # stable, citable: "b1", "b2", ...
    type: Literal["heading", "para", "list", "table", "caption"]
    text: str
    page: int | None = None


class Asset(BaseModel):
    id: str
    kind: Literal["image", "table", "chart"]
    path: str
    caption: str | None = None


class SourceDocument(BaseModel):
    doc_id: str
    markdown: str  # normalised body, headings preserved
    blocks: list[Block]  # citation targets for grounding
    assets: list[Asset]
    meta: dict  # title, source_url, mime, ingested_at
