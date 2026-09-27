"""Shared by every ingester: ordered blocks in, SourceDocument out.

An ingester only decides what the blocks are. Ids, the markdown body, doc_id
and meta are assigned here, so they follow the same rules for every input type.
"""

import hashlib
from datetime import UTC, datetime
from typing import NamedTuple

from app.ingest.base import Block, SourceDocument


class IngestError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status  # HTTP status the API layer should answer with


class Part(NamedTuple):
    type: str  # a Block type
    text: str  # the block's text, as the brief prompt and citations show it
    markdown: str  # how the block appears in SourceDocument.markdown
    page: int | None = None


def markdown_table(rows: list[list[str]]) -> str:
    """Cell text in, a markdown table out; "" if every cell is empty. The first row is the header."""
    rows = [[" ".join(c.split()).replace("|", "\\|") for c in r] for r in rows]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    lines = ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return "\n".join(lines)


def assemble(parts: list[Part], mime: str, fallback_title: str | None = None) -> SourceDocument:
    """Blocks get ids b1, b2, ... in order. The title is the first heading, else `fallback_title`."""
    blocks = [
        Block(id=f"b{i}", type=p.type, text=p.text, page=p.page) for i, p in enumerate(parts, start=1)
    ]
    title = next((b.text for b in blocks if b.type == "heading"), None) or fallback_title
    markdown = "\n\n".join(p.markdown for p in parts)
    return SourceDocument(
        doc_id="doc_" + hashlib.sha256(markdown.encode()).hexdigest()[:12],
        markdown=markdown,
        blocks=blocks,
        assets=[],
        meta={
            "title": title,
            "source_url": None,
            "mime": mime,
            "ingested_at": datetime.now(UTC).isoformat(),
        },
    )
