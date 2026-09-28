"""Jinja HTML templates to PDF bytes with WeasyPrint. No model calls.

Templates are in render/templates/ and extend base.html, which takes its
colours, font, organisation name and logo from a Theme (render/theme.py). What
a template shows comes from a validated payload, which is model output, so
Jinja autoescapes everything.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.render.theme import Theme

TEMPLATES = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=True,
    undefined=StrictUndefined,  # a misspelt field fails the render instead of printing nothing
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_pdf(template: str, theme: Theme, **context) -> bytes:
    # Imported here, not at the top: WeasyPrint needs Pango, and without it
    # only the PDF formats should fail, not the server or the other formats.
    try:
        from weasyprint import HTML
        from weasyprint.urls import URLFetcher
    except OSError as e:
        raise RuntimeError(
            "PDF rendering needs Pango: `brew install pango` and "
            "DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib in .env (see README)."
        ) from e

    html = _env.get_template(template).render(theme=theme, **context)
    # Templates load nothing external: the only image, a brand kit's logo, is
    # inlined as a data: URI. Allowing that scheme alone means text in a
    # payload can never make the renderer read a file or the network.
    return HTML(string=html, url_fetcher=URLFetcher(allowed_protocols=("data",))).write_pdf()
