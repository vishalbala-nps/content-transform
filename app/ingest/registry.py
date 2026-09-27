"""Uploaded file -> SourceDocument, chosen by file extension.

Adding an input type is one ingester module plus one line here. The API and the
UI read the accepted extensions from this table, so neither needs an edit.
"""

from collections.abc import Callable
from pathlib import PurePath

from app.ingest.base import SourceDocument
from app.ingest.common import IngestError
from app.ingest.docx import ingest_docx
from app.ingest.html import ingest_html
from app.ingest.pdf import ingest_pdf
from app.ingest.text import ingest_text


def _ingest_text_file(data: bytes) -> SourceDocument:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise IngestError("Text files must be UTF-8.") from e
    return ingest_text(text)


INGESTERS: dict[str, Callable[[bytes], SourceDocument]] = {
    ".txt": _ingest_text_file,
    ".md": _ingest_text_file,
    ".docx": ingest_docx,
    ".pdf": ingest_pdf,
    ".html": ingest_html,
    ".htm": ingest_html,
}


def ingest_file(filename: str, data: bytes) -> SourceDocument:
    ingester = INGESTERS.get(PurePath(filename).suffix.lower())
    if ingester is None:
        raise IngestError(
            f"Unsupported file type: {filename!r}. Accepted: {', '.join(INGESTERS)}.", status=415
        )
    doc = ingester(data)
    doc.meta["filename"] = filename
    return doc
