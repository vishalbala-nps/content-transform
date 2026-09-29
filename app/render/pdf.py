"""Jinja HTML templates to PDF bytes with WeasyPrint. No model calls.

Templates are in render/templates/ and extend base.html, which takes its
colours, font, organisation name and logo from a Theme (render/theme.py). What
a template shows comes from a validated payload, which is model output, so
Jinja autoescapes everything.
"""

import base64
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.render.labels import label, page_counter_css
from app.render.theme import Theme

TEMPLATES = Path(__file__).parent / "templates"
FONTS = Path(__file__).parent / "fonts"

# Noto Sans for each output language's script (SIL Open Font License, see
# fonts/OFL.txt), bundled so a PDF looks the same on any machine. System
# fallbacks such as Arial Unicode MS cannot shape these scripts: Telugu and
# Kannada vowel signs come apart.
SCRIPT_FONTS = {
    "hi": "Noto Sans Devanagari",
    "ta": "Noto Sans Tamil",
    "ml": "Noto Sans Malayalam",
    "kn": "Noto Sans Kannada",
    "te": "Noto Sans Telugu",
}

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=True,
    undefined=StrictUndefined,  # a misspelt field fails the render instead of printing nothing
    trim_blocks=True,
    lstrip_blocks=True,
)


@cache
def _font_faces(family: str) -> str:
    """@font-face rules for a bundled family, as data: URIs, the only URL
    scheme the renderer may load."""
    stem = family.replace(" ", "")
    rules = []
    for weight, style in ((400, "Regular"), (700, "Bold")):
        data = base64.b64encode((FONTS / f"{stem}-{style}.ttf").read_bytes()).decode()
        rules.append(
            f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
            f'src: url(data:font/ttf;base64,{data}) format("truetype"); }}'
        )
    return "\n".join(rules)


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

    lang = context.get("lang", "en")
    family = SCRIPT_FONTS.get(lang)
    html = _env.get_template(template).render(
        theme=theme,
        fonts=theme.css_fonts_with(family),
        font_faces=_font_faces(family) if family else "",
        t=lambda text: label(text, lang),  # fixed labels in the output language (labels.json)
        page_counter=page_counter_css(lang),
        **context,
    )
    # Templates load nothing external: the only image, a brand kit's logo, is
    # inlined as a data: URI. Allowing that scheme alone means text in a
    # payload can never make the renderer read a file or the network.
    return HTML(string=html, url_fetcher=URLFetcher(allowed_protocols=("data",))).write_pdf()
