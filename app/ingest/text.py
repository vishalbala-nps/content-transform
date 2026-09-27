"""Plain text / markdown ingester.

Blocks are split on blank lines. A block whose first line starts with `#` is a
heading; a block whose every line is a bullet or numbered item is a list.
"""

import hashlib
import re
from datetime import UTC, datetime

from app.ingest.base import Block, SourceDocument

_LIST_ITEM = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")


def _block_type(chunk: str) -> str:
    if chunk.startswith("#"):
        return "heading"
    if all(_LIST_ITEM.match(line) for line in chunk.splitlines()):
        return "list"
    return "para"


def ingest_text(text: str) -> SourceDocument:
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks = [c.strip() for c in re.split(r"\n\s*\n", normalised) if c.strip()]

    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        kind = _block_type(chunk)
        body = chunk.lstrip("#").strip() if kind == "heading" else chunk
        blocks.append(Block(id=f"b{i}", type=kind, text=body))

    title = next((b.text for b in blocks if b.type == "heading"), None)
    markdown = "\n\n".join(chunks)
    return SourceDocument(
        doc_id="doc_" + hashlib.sha256(markdown.encode()).hexdigest()[:12],
        markdown=markdown,
        blocks=blocks,
        assets=[],
        meta={
            "title": title,
            "source_url": None,
            "mime": "text/plain",
            "ingested_at": datetime.now(UTC).isoformat(),
        },
    )
