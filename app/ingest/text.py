"""Plain text / markdown ingester.

Blocks are split on blank lines. A block whose first line starts with `#` is a
heading; a block whose every line is a bullet or numbered item is a list.
"""

import re

from app.ingest.base import SourceDocument
from app.ingest.common import Part, assemble

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

    parts = []
    for chunk in chunks:
        kind = _block_type(chunk)
        body = chunk.lstrip("#").strip() if kind == "heading" else chunk
        parts.append(Part(kind, body, chunk))
    return assemble(parts, mime="text/plain")
