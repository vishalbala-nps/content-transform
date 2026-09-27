"""PDF ingester for PDFs with a text layer. PyMuPDF reads the text; no model involved.

Every block carries its 1-based page number. Structure comes from the layout:

- Headings: lines set noticeably larger than the body text (levels by size),
  or a short standalone bold line at body size, as advisories label sections.
- Lists: lines starting with a bullet or number; also an indented block of
  short lines, since some producers (Chrome, for one) draw bullets as graphics.
- Tables: found by PyMuPDF's table finder and written as markdown tables.
  Their text is not repeated as paragraphs. A "table" with many columns or
  mostly empty cells is a figure or a layout grid; its text is read as text.
- Running headers and footers (the same text in the top or bottom margin of
  most pages, page numbers aside) are dropped.

Blocks are taken in the order the PDF stores them, which for most producers is
reading order, including multi-column layouts. A paragraph split by a page
break becomes two blocks. A word hyphenated across lines keeps its hyphen.
Vertical text (margin notes such as arXiv ids) and images are ignored: a PDF
with no text layer (a scan) is refused, and pages without text are listed in
`meta["pages_without_text"]`. The title is the largest heading on page 1.
"""

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from app.ingest.base import SourceDocument
from app.ingest.common import IngestError, Part, assemble, markdown_table

log = logging.getLogger(__name__)

pymupdf.no_recommend_layout()  # otherwise it prints an install hint to stdout

MIME = "application/pdf"

HEADING_RATIO = 1.15  # a line this much larger than the body text is a heading
MARGIN_ZONE = 0.08  # top and bottom fraction of the page where running heads live
MIN_PAGE_CHARS = 20  # a page with less text than this counts as having none
MAX_TABLE_COLUMNS = 12

_BULLET = re.compile(r"(?:[•·▪◦‣●○■□]\s*|[–*-]\s+)")
_NUMBER = re.compile(r"\d{1,2}[.)]\s+")
_BOLD = 1 << 4
# Metadata titles that name the file or the program rather than the document.
_JUNK_TITLE = re.compile(r"(?i)^(microsoft\s+\w+\s+-|untitled)|\.(docx?|pdf|pptx?)$")


@dataclass
class _Line:
    text: str
    size: float
    bold: bool
    x0: float
    x1: float
    y0: float
    y1: float


@dataclass
class _Block:
    lines: list[_Line]
    x0: float
    x1: float
    y0: float


@dataclass
class _Table:
    markdown: str


def _line(raw: dict) -> _Line | None:
    spans = [s for s in raw["spans"] if s["text"].strip()]
    if not spans or abs(raw["dir"][1]) > 0.1:  # empty, or not horizontal
        return None
    text = " ".join("".join(s["text"] for s in raw["spans"]).split())
    x0, y0, x1, y1 = raw["bbox"]
    return _Line(
        text=text,
        size=max(s["size"] for s in spans),
        bold=all(s["flags"] & _BOLD or "bold" in s["font"].lower() for s in spans),
        x0=x0,
        x1=x1,
        y0=y0,
        y1=y1,
    )


def _inside(line: _Line, bbox: tuple) -> bool:
    cx, cy = (line.x0 + line.x1) / 2, (line.y0 + line.y1) / 2
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


def _table_rows(table: pymupdf.table.Table) -> list[list[str]] | None:
    """The cell text, or None when the table finder has picked up a figure or a layout grid."""
    rows = [[" ".join((cell or "").split()) for cell in row] for row in table.extract()]
    cells = [c for r in rows for c in r]
    if not cells or table.col_count > MAX_TABLE_COLUMNS or sum(not c for c in cells) > len(cells) / 2:
        return None
    return rows


def _read_page(page: pymupdf.Page) -> list[_Block | _Table]:
    """The page's text blocks and tables, in stored order, tables placed by position."""
    tables = []
    for table in page.find_tables().tables:
        rows = _table_rows(table)
        if rows:
            tables.append((table.bbox, markdown_table(rows)))
    blocks = []
    for raw in page.get_text("dict")["blocks"]:
        if raw["type"] != 0:
            continue  # an image
        lines = [ln for ln in map(_line, raw["lines"]) if ln]
        lines = [ln for ln in lines if not any(_inside(ln, bbox) for bbox, _ in tables)]
        if lines:
            blocks.append(
                _Block(lines, min(ln.x0 for ln in lines), max(ln.x1 for ln in lines), lines[0].y0)
            )

    items: list[_Block | _Table] = list(blocks)
    for bbox, md in sorted(tables, key=lambda t: t[0][1]):
        # Before the first text block that starts below the table's top edge.
        at = next((i for i, b in enumerate(items) if isinstance(b, _Block) and b.y0 > bbox[1]), None)
        items.insert(len(items) if at is None else at, _Table(md))
    return items


def _running_head_key(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower())


def _drop_running_heads(pages: list[list[_Block | _Table]], heights: list[float]) -> None:
    """Remove lines repeated in the top or bottom margin of most pages. Needs two pages or more."""
    if len(pages) < 2:
        return

    def in_margin(line: _Line, height: float) -> bool:
        return line.y1 < height * MARGIN_ZONE or line.y0 > height * (1 - MARGIN_ZONE)

    seen = Counter()
    for items, height in zip(pages, heights):
        keys = {
            _running_head_key(ln.text)
            for b in items
            if isinstance(b, _Block)
            for ln in b.lines
            if in_margin(ln, height)
        }
        seen.update(keys)
    threshold = max(2, math.ceil(len(pages) / 2))
    repeated = {k for k, n in seen.items() if n >= threshold}
    if not repeated:
        return
    for items, height in zip(pages, heights):
        for b in items:
            if isinstance(b, _Block):
                b.lines = [
                    ln
                    for ln in b.lines
                    if not (in_margin(ln, height) and _running_head_key(ln.text) in repeated)
                ]
        items[:] = [b for b in items if isinstance(b, _Table) or b.lines]


def _body_size(pages: list[list[_Block | _Table]]) -> float:
    """The most common text size, weighted by characters."""
    sizes = Counter()
    for items in pages:
        for b in items:
            if isinstance(b, _Block):
                for ln in b.lines:
                    sizes[round(ln.size * 2) / 2] += len(ln.text)
    return sizes.most_common(1)[0][0] if sizes else 0.0


class _Layout:
    """Document-wide measurements the per-block rules compare against."""

    def __init__(self, pages: list[list[_Block | _Table]]):
        self.body = _body_size(pages)
        body_lines = [
            ln
            for items in pages
            for b in items
            if isinstance(b, _Block)
            for ln in b.lines
            if abs(ln.size - self.body) < 0.6
        ]
        # Left edge and right edge of the text column: the most common line start,
        # and a high percentile of line ends (wrapped lines run to the edge).
        starts = Counter(round(ln.x0) for ln in body_lines)
        self.left = starts.most_common(1)[0][0] if starts else 0.0
        ends = sorted(ln.x1 for ln in body_lines)
        self.right = ends[int(len(ends) * 0.9)] if ends else 0.0
        heading_sizes = sorted(
            {
                round(ln.size * 2) / 2
                for items in pages
                for b in items
                if isinstance(b, _Block)
                for ln in b.lines
                if self.is_heading_size(ln)
            },
            reverse=True,
        )
        self.levels = {size: min(i + 1, 6) for i, size in enumerate(heading_sizes)}
        self.bold_level = min(len(heading_sizes) + 1, 6)

    def is_heading_size(self, line: _Line) -> bool:
        return line.size >= self.body * HEADING_RATIO and len(line.text) <= 200

    def level(self, line: _Line) -> int:
        return self.levels.get(round(line.size * 2) / 2, 1)


def _join(text: str, line: str) -> str:
    """Append a wrapped line. A hyphen at the break stays, without a space after it."""
    return text + line if text.endswith("-") else text + " " + line


def _is_marked(text: str) -> bool:
    return bool(_BULLET.match(text) or _NUMBER.match(text))


def _list_line(text: str) -> str:
    if _NUMBER.match(text):
        return text
    return "- " + _BULLET.sub("", text, count=1)


def _body_parts(lines: list[_Line], block: _Block, layout: _Layout, page: int) -> list[Part]:
    """Body-size lines of one block as a paragraph or a list."""
    # The right edge lines wrap at: the block's own when most of its lines
    # reach it (a wrapped paragraph, in any column), else the text column's.
    right = block.x1
    near_edge = [ln for ln in lines[:-1] if ln.x1 >= right - 0.1 * (right - block.x0)]
    if len(lines) < 3 or len(near_edge) < 2 / 3 * (len(lines) - 1):
        right = max(block.x1, layout.right)

    def breaks_after(i: int) -> bool:
        """Line i ends on purpose if the next line's first word would have fitted after it."""
        line, following = lines[i], lines[i + 1]
        char_width = (following.x1 - following.x0) / len(following.text)
        return right - line.x1 > char_width * (len(following.text.split()[0]) + 1)

    if _is_marked(lines[0].text):
        items: list[str] = []
        for ln in lines:
            if _is_marked(ln.text) or not items:
                items.append(ln.text)
            else:
                items[-1] = _join(items[-1], ln.text)  # an item's wrapped continuation
        text = "\n".join(_list_line(i) for i in items)
        return [Part("list", text, text, page)]

    indented = block.x0 > layout.left + 6
    if indented and len(lines) >= 2 and all(breaks_after(i) for i in range(len(lines) - 1)):
        text = "\n".join(f"- {ln.text}" for ln in lines)
        return [Part("list", text, text, page)]

    text = lines[0].text
    for i, ln in enumerate(lines[1:], start=1):
        text = text + "\n" + ln.text if breaks_after(i - 1) else _join(text, ln.text)
    return [Part("para", text, text, page)]


def _block_parts(block: _Block, layout: _Layout, page: int) -> list[Part]:
    lines = block.lines
    short_bold = (
        len(lines) <= 2
        and all(ln.bold for ln in lines)
        and sum(len(ln.text) for ln in lines) <= 100
        and not lines[-1].text.endswith(".")
    )
    if short_bold and not any(layout.is_heading_size(ln) for ln in lines):
        text = " ".join(ln.text for ln in lines)
        return [Part("heading", text, "#" * layout.bold_level + " " + text, page)]

    parts: list[Part] = []
    run: list[_Line] = []  # consecutive lines of the same kind

    def flush() -> None:
        if not run:
            return
        if layout.is_heading_size(run[0]):
            level = layout.level(run[0])
            text = " ".join(ln.text for ln in run)  # a wrapped heading
            parts.append(Part("heading", text, "#" * level + " " + text, page))
        else:
            parts.extend(_body_parts(run, block, layout, page))
        run.clear()

    def kind(line: _Line) -> float | None:
        """Heading lines group by size; all body lines group together."""
        return line.size if layout.is_heading_size(line) else None

    for ln in lines:
        if run and kind(ln) != kind(run[0]):
            flush()
        run.append(ln)
    flush()
    return parts


def _merge_lists(parts: list[Part]) -> list[Part]:
    """Join neighbouring list blocks on one page when both are bulleted or both numbered.

    Producers often store each list item as its own block.
    """
    merged: list[Part] = []
    for part in parts:
        prev = merged[-1] if merged else None
        if (
            prev
            and part.type == prev.type == "list"
            and part.page == prev.page
            and part.text[0].isdigit() == prev.text[0].isdigit()
        ):
            text = prev.text + "\n" + part.text
            merged[-1] = Part("list", text, text, part.page)
        else:
            merged.append(part)
    return merged


def _page_one_title(parts: list[Part]) -> str | None:
    """The first page-1 heading at the top level; the first heading may be a notice or banner."""
    headings = [
        (len(p.markdown) - len(p.markdown.lstrip("#")), p.text)
        for p in parts
        if p.type == "heading" and p.page == 1
    ]
    return min(headings, key=lambda h: h[0])[1] if headings else None


def ingest_pdf(data: bytes) -> SourceDocument:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as e:
        raise IngestError("This is not a readable PDF file.") from e
    with doc:
        if doc.needs_pass:
            raise IngestError("This PDF is password-protected.")
        pages = [_read_page(page) for page in doc]
        heights = [page.rect.height for page in doc]
        meta_title = (doc.metadata or {}).get("title") or ""

    # After running heads go, so a scanned page stamped with a header still counts as empty.
    _drop_running_heads(pages, heights)
    empty = [
        i
        for i, items in enumerate(pages, start=1)
        if sum(len(ln.text) for b in items if isinstance(b, _Block) for ln in b.lines)
        + sum(len(b.markdown) for b in items if isinstance(b, _Table))
        < MIN_PAGE_CHARS
    ]
    if len(empty) == len(pages):
        raise IngestError(
            "This PDF has no text layer; it is probably scanned. Scanned documents are not supported yet."
        )

    layout = _Layout(pages)
    parts: list[Part] = []
    for page_no, items in enumerate(pages, start=1):
        for item in items:
            if isinstance(item, _Table):
                parts.append(Part("table", item.markdown, item.markdown, page_no))
            else:
                parts.extend(_block_parts(item, layout, page_no))

    parts = _merge_lists(parts)
    fallback = meta_title.strip() if meta_title.strip() and not _JUNK_TITLE.search(meta_title) else None
    source = assemble(parts, mime=MIME, fallback_title=fallback)
    source.meta["title"] = _page_one_title(parts) or source.meta["title"]
    if empty:
        log.warning("PDF pages without text, skipped: %s", empty)
        source.meta["pages_without_text"] = empty
    return source
