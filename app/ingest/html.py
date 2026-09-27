"""HTML ingester. trafilatura strips navigation and boilerplate; no model involved.

trafilatura's XML output marks the structure it keeps, and each element maps to
a block: `head` is a heading, `p` a paragraph, `list` a list, and a `table` of
plain cells a markdown table. A paragraph that is entirely bold and short is a
heading, as section labels often are. Text lying between elements becomes a
paragraph of its own. Line breaks inside a paragraph are kept.

Older sites lay pages out with tables. A table whose cells hold paragraphs or
headings is layout, not data, and is read as the content it contains. When
one such cell holds most of the page's text it is the article, and the other
cells (navigation, footers, which trafilatura keeps on these pages) are
dropped. Headings styled only with CSS are not visible here and stay paragraphs.

trafilatura can drop headings at the top of a page with no <article> or <main>
around its content. The page's first <h1> is its title (unlike <title>, which
is often a section name), so if it was dropped it goes back in as the first
heading. Bracketed fragments such as "[edit]" are skipped.

Short "enable JavaScript" notices (usually a <noscript> block) are dropped. A
page with little else is one whose content is built by JavaScript, or loaded
in a frame, and nothing here runs either; it is refused rather than passed on
as a source that is only a notice and a menu.
"""

import re

import lxml.html
import trafilatura
from lxml import etree

from app.ingest.base import SourceDocument
from app.ingest.common import IngestError, Part, assemble, markdown_table

MIME = "text/html"

BOLD_HEADING_LEVEL = 3
MAX_BOLD_HEADING_CHARS = 100
MAIN_CELL_SHARE = 0.6  # a layout cell with this share of the text is the article

_BRACKETED = re.compile(r"\[[^\]]{0,15}\]")  # "[edit]", "[1]": page furniture, not content

MAX_NOTICE_CHARS = 400
# Paragraph and table text a page needs besides a JavaScript notice. Menus
# arrive as lists and headings are short, so neither counts.
MIN_CONTENT_CHARS = 200
_JAVASCRIPT = re.compile(r"(?i)\bjavascript\b")
_NOTICE_VERB = re.compile(
    r"(?i)\b(enable|enabled|disabled|required|requires|require|needs?|must be|turn on|switch on)\b"
)

_CONTAINERS = {"main", "div", "cell", "quote", "section"}
_BLOCKS = {"head", "p", "list", "table", "quote", "code", "div"}


def _chars(el: etree._Element) -> int:
    return sum(len("".join(t.split())) for t in el.itertext())


def _inline_text(el: etree._Element) -> str:
    """An element's text, `<lb/>` as a line break, whitespace normalised per line."""
    pieces = [el.text or ""]
    for child in el:
        if child.tag == "lb":
            pieces.append("\n")
        else:
            inner = _inline_text(child)
            pieces.append(inner)
            # "<b>Impact:</b>There is..." needs a space once the bold is gone.
            if inner.endswith(":") and child.tail and not child.tail[0].isspace():
                pieces.append(" ")
        pieces.append(child.tail or "")
    lines = (" ".join(line.split()) for line in "".join(pieces).split("\n"))
    return "\n".join(line for line in lines if line)


def _is_bold_label(el: etree._Element, text: str) -> bool:
    """The whole element is one bold run, short, and not a sentence."""
    if el.tag == "hi":
        bold = "#b" in (el.get("rend") or "")
    else:
        children = [c for c in el if c.tag != "lb"]
        bold = (
            len(children) == 1
            and children[0].tag == "hi"
            and "#b" in (children[0].get("rend") or "")
            and not (el.text or "").strip()
            and not (children[0].tail or "").strip()
        )
    return bold and "\n" not in text and len(text) <= MAX_BOLD_HEADING_CHARS and not text.endswith(".")


def _is_layout_table(table: etree._Element) -> bool:
    cells = table.findall("row/cell")
    if any(child.tag in _BLOCKS for cell in cells for child in cell):
        return True
    return all(len(row.findall("cell")) <= 1 for row in table.findall("row"))


def _main_cell(main: etree._Element) -> etree._Element:
    """The innermost layout cell holding most of the text, if there is one; else `main`."""
    total = _chars(main)
    candidates = [
        cell
        for cell in main.iter("cell")
        if any(child.tag in _BLOCKS for child in cell) and _chars(cell) >= MAIN_CELL_SHARE * total
    ]
    return min(candidates, key=_chars) if candidates else main


def _is_javascript_notice(part: Part) -> bool:
    return (
        len(part.text) <= MAX_NOTICE_CHARS
        and bool(_JAVASCRIPT.search(part.text))
        and bool(_NOTICE_VERB.search(part.text))
    )


def _first_h1(data: bytes) -> str | None:
    try:
        page = lxml.html.fromstring(data)
    except (etree.ParserError, ValueError):
        return None
    h1 = next(page.iter("h1"), None)
    text = " ".join(h1.text_content().split()) if h1 is not None else ""
    return text or None


class _Walker:
    def __init__(self) -> None:
        self.parts: list[Part] = []

    def text(self, text: str) -> None:
        text = "\n".join(" ".join(line.split()) for line in text.split("\n") if line.strip())
        if text and not _BRACKETED.fullmatch(text):
            self.parts.append(Part("para", text, text))

    def heading(self, text: str, level: int) -> None:
        text = " ".join(text.split())
        if text:
            self.parts.append(Part("heading", text, "#" * level + " " + text))

    def container(self, el: etree._Element) -> None:
        self.text(el.text or "")
        for child in el:
            self.element(child)
            self.text(child.tail or "")

    def element(self, el: etree._Element) -> None:
        if el.tag in _CONTAINERS:
            self.container(el)
        elif el.tag == "head":
            rend = el.get("rend") or ""
            level = int(rend[1]) if len(rend) == 2 and rend[0] == "h" and rend[1].isdigit() else 2
            self.heading(_inline_text(el), level)
        elif el.tag == "list":
            self.list(el)
        elif el.tag == "table":
            self.table(el)
        elif el.tag in ("lb", "graphic"):
            pass
        else:  # p, code, and inline elements (hi, ref) standing on their own
            text = _inline_text(el)
            if _is_bold_label(el, text):
                self.heading(text, BOLD_HEADING_LEVEL)
            else:
                self.text(text)

    def list(self, el: etree._Element) -> None:
        # A nested list is flattened into its parent item's text.
        items = [" ".join("".join(item.itertext()).split()) for item in el.findall("item")]
        items = [i for i in items if i]
        numbered = el.get("rend") == "ol"
        lines = [f"{n}. {i}" if numbered else f"- {i}" for n, i in enumerate(items, start=1)]
        if lines:
            text = "\n".join(lines)
            self.parts.append(Part("list", text, text))

    def table(self, el: etree._Element) -> None:
        if _is_layout_table(el):
            for cell in el.iterfind("row/cell"):
                self.container(cell)
            return
        rows = [[_inline_text(cell) for cell in row.findall("cell")] for row in el.findall("row")]
        md = markdown_table(rows)
        if md:
            self.parts.append(Part("table", md, md))


def ingest_html(data: bytes) -> SourceDocument:
    # trafilatura detects the encoding from the bytes and the page's own declarations.
    xml = trafilatura.extract(
        data,
        output_format="xml",
        include_tables=True,
        include_formatting=True,  # bold marks section labels
        include_comments=False,
        include_links=False,
        with_metadata=True,
        # Precision mode dropped whole lists (an advisory's affected versions) and,
        # on CERT-In's table layout, most of the advisory.
        favor_recall=True,
    )
    if not xml:
        raise IngestError("No readable text found in this page.")
    doc = etree.fromstring(xml)
    main = doc.find("main")
    walker = _Walker()
    if main is not None:
        walker.container(_main_cell(main))
    parts = [p for p in walker.parts if not _is_javascript_notice(p)]
    if len(parts) < len(walker.parts):
        content = sum(len(p.text) for p in parts if p.type in ("para", "table"))
        if content < MIN_CONTENT_CHARS:
            raise IngestError(
                "This page needs JavaScript to show its content, which is not supported. "
                "Paste the text, or save the page as PDF from your browser and upload that."
            )
    h1 = _first_h1(data)
    if h1 and parts and not any(h1 in part.text for part in parts):
        parts.insert(0, Part("heading", h1, f"# {h1}"))
    return assemble(parts, mime=MIME, fallback_title=doc.get("title") or None)
