"""URL -> SourceDocument: download the page, then ingest it like an uploaded file.

The response's content type picks the ingester, so a link to a PDF goes through
the PDF ingester; the URL's own extension is the fallback.

Only public addresses are fetched: every request, redirects included, has
its host resolved first, and a private, loopback, link-local or otherwise
non-public address is refused, so a signed-in user cannot make the server
read its own network. `ALLOW_PRIVATE_URLS=1` lifts this for an intranet.
The check and the connection each resolve the name, so a DNS server that
answers differently the second time could still get through; closing that
needs connecting to the checked address itself.
"""

import asyncio
import ipaddress
import socket
from pathlib import PurePath
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings
from app.ingest import docx, html, pdf
from app.ingest.base import SourceDocument
from app.ingest.common import MAX_FILE_BYTES, IngestError
from app.ingest.registry import INGESTERS, ingest_file

TIMEOUT_S = 20
# Some sites refuse requests without a browser-like user agent.
USER_AGENT = "Mozilla/5.0 (compatible; Spectra/0.1)"

_EXTENSIONS = {
    html.MIME: ".html",
    "application/xhtml+xml": ".html",
    pdf.MIME: ".pdf",
    docx.MIME: ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
}


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])  # drop an IPv6 zone id
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


async def _refuse_private(request: httpx.Request) -> None:
    """httpx calls this before every request it sends, redirects included."""
    if get_settings().allow_private_urls:
        return
    host = request.url.host
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, request.url.port or 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise IngestError(f"Could not find {host}.", status=502) from e
    if not all(_public(info[4][0]) for info in infos):
        raise IngestError(
            f"{host} is on a private network, which link sources may not reach. "
            "Download the page and upload it instead.",
            status=422,
        )


async def _download(url: str) -> tuple[bytes, str, str]:
    """The body, its content type and the final URL after redirects."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=TIMEOUT_S,
            headers={"User-Agent": USER_AGENT},
            event_hooks={"request": [_refuse_private]},
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
