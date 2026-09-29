"""Fixed labels in rendered files ("Key points", "Page 1 of 3"), per output language.

The English text is the key, so code reads as English: `label("Key points",
lang)`. Translations are in labels.json, checked in and meant to be read by a
native speaker. They are filled by `python -m tools.translate_labels`, never at
render time: render/ does not call models.

A label missing from labels.json raises KeyError in every language, English
included, so a new label is caught the first time it renders, not only when
someone picks Tamil.
"""

import json
from functools import cache
from pathlib import Path

FILE = Path(__file__).parent / "labels.json"


@cache
def _labels() -> dict[str, dict[str, str]]:
    return json.loads(FILE.read_text())


def label(text: str, lang: str) -> str:
    translations = _labels()[text]
    return text if lang == "en" else translations[lang]


def page_counter_css(lang: str) -> str:
    """CSS `content` for the page footer, e.g. "Page " counter(page) " of " counter(pages).
    Word order differs by language, so the label carries {page} and {pages}."""
    template = label("Page {page} of {pages}", lang)
    parts, rest = [], template
    while rest:
        at = min((i for i in (rest.find("{page}"), rest.find("{pages}")) if i >= 0), default=-1)
        if at < 0:
            parts.append(_css_string(rest))
            break
        if at:
            parts.append(_css_string(rest[:at]))
        token = "{pages}" if rest.startswith("{pages}", at) else "{page}"
        parts.append("counter(pages)" if token == "{pages}" else "counter(page)")
        rest = rest[at + len(token) :]
    return " ".join(parts)


def _css_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
