"""URL -> SourceDocument: download the page, then ingest it like an uploaded file.

The response's content type picks the ingester, so a link to a PDF goes through
the PDF ingester; the URL's own extension is the fallback. The server fetches
whatever URL it is given, including addresses on its own network, which is
fine for a tool run locally and a reason not to expose it publicly.
"""

import asyncio
from pathlib import PurePath
from urllib.parse import urlsplit

import httpx

from app.ingest import docx, html, pdf
from app.ingest.base import SourceDocument
from app.ingest.common import MAX_FILE_BYTES, IngestError
from app.ingest.registry import INGESTERS, ingest_file

TIMEOUT_S = 20
# Some sites refuse requests without a browser-like user agent.
USER_AGENT = "Mozilla/5.0 (compatible; content-transform/0.1)"

_EXTENSIONS = {
    html.MIME: ".html",
    "application/xhtml+xml": ".html",
    pdf.MIME: ".pdf",
    docx.MIME: ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
}


async def _download(url: str) -> tuple[bytes, str, str]:
    """The body, its content type and the final URL after redirects."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT}
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise IngestError(f"The page answered HTTP {response.status_code}.")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise IngestError(
                            f"The page is larger than {MAX_FILE_BYTES // 2**20} MB.", status=413
                        )
                    chunks.append(chunk)
                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                return b"".join(chunks), content_type, str(response.url)
    except httpx.TimeoutException as e:
        raise IngestError(f"The page did not respond within {TIMEOUT_S} s.", status=504) from e
    except httpx.HTTPError as e:
        raise IngestError(f"Could not fetch the page: {e}", status=502) from e


async def ingest_url(url: str) -> SourceDocument:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise IngestError("Enter a full URL starting with http:// or https://.")

    data, content_type, final_url = await _download(url)
    path = PurePath(urlsplit(final_url).path)
    extension = _EXTENSIONS.get(content_type) or path.suffix.lower()
    if extension not in INGESTERS:
        raise IngestError(f"Unsupported content at that URL ({content_type or 'unknown type'}).", status=415)

    # Parsing is CPU-bound; off the event loop so progress streams keep flowing.
    source = await asyncio.to_thread(ingest_file, (path.stem or "page") + extension, data)
    del source.meta["filename"]  # a name made up from the URL; the URL says more
    source.meta["source_url"] = final_url
    return source
