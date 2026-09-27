"""DOCX ingester. python-docx reads the body in document order; no model involved.

- Paragraph styles give the structure: "Title" and "Heading N" become headings,
  and paragraphs in a "List ..." style or with Word numbering become list
  items, as do paragraphs that start with a typed bullet or number. Consecutive
  items of the same list form one list block, as in the text ingester.
  Headings made only with bold or large text are not detected.
- Each table is one block, written as a markdown table. A merged cell is
  written once, with empty cells for the other columns it spans.
- Headers, footers, comments, text boxes and images are ignored. A DOCX has no
  pages, so blocks carry no page number.
"""

import io
import re
import zipfile

import docx
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingest.base import SourceDocument
from app.ingest.common import IngestError, Part, assemble

MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_HEADING_STYLE = re.compile(r"Heading (\d)")
_TYPED_BULLET = re.compile(r"[•·▪◦‣●○■□–*-]\s+")
_TYPED_NUMBER = re.compile(r"\d+[.)]\s+")


def _clean(text: str) -> str:
    return " ".join(text.split())


def _heading_level(p: Paragraph) -> int | None:
    name = p.style.name if p.style is not None else ""
    if name == "Title":
        return 1
    match = _HEADING_STYLE.fullmatch(name)
    return int(match.group(1)) if match else None


def _list_key(p: Paragraph, text: str) -> str | None:
    """Which list the paragraph belongs to, or None if it is not a list item."""
    ppr = p._p.pPr
    if ppr is not None and ppr.numPr is not None and ppr.numPr.numId is not None:
        return f"num:{ppr.numPr.numId.val}"
    if p.style is not None and p.style.name.startswith("List"):
        return f"style:{p.style.name}"
    if _TYPED_BULLET.match(text) or _TYPED_NUMBER.match(text):
        return "typed"
    return None


def _list_line(text: str) -> str:
    if _TYPED_NUMBER.match(text):
        return text
    return "- " + _TYPED_BULLET.sub("", text, count=1)


def _table_markdown(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells, prev = [], None
        for cell in row.cells:
            # A merged cell is returned once per grid column it spans.
            cells.append("" if cell._tc is prev else _clean(cell.text).replace("|", "\\|"))
            prev = cell._tc
        rows.append(cells)
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(r) + " |" for r in rows]
    lines.insert(1, "|" + " --- |" * width)
    return "\n".join(lines)


def ingest_docx(data: bytes) -> SourceDocument:
    try:
        document = docx.Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError, PackageNotFoundError) as e:
        raise IngestError("This is not a readable .docx file.") from e

    parts: list[Part] = []
    items: list[str] = []  # lines of the list being collected
    current_list: str | None = None

    def end_list() -> None:
        nonlocal current_list
        if items:
            text = "\n".join(items)
            parts.append(Part("list", text, text))
            items.clear()
        current_list = None

    for element in document.iter_inner_content():
        if isinstance(element, Table):
            end_list()
            table = _table_markdown(element)
            if table:
                parts.append(Part("table", table, table))
            continue
        text = _clean(element.text)
        if not text:
            continue  # an empty paragraph does not end a list
        level = _heading_level(element)
        key = None if level else _list_key(element, text)
        if level:
            end_list()
            parts.append(Part("heading", text, "#" * level + " " + text))
        elif key:
            if key != current_list:
                end_list()
                current_list = key
            items.append(_list_line(text))
        else:
            end_list()
            parts.append(Part("para", text, text))
    end_list()

    return assemble(parts, mime=MIME, fallback_title=document.core_properties.title or None)
