"""Fill in missing translations in app/render/labels.json with the model.

    uv run --env-file .env python -m tools.translate_labels [--redo] [--languages hi,ta]

Add a new label to labels.json with an empty entry ({}), run this, then have
the new lines read by a native speaker before relying on them. Existing
translations are kept unless --redo is given, so a correction made by hand
is never overwritten. A developer tool: nothing in app/ runs it.
"""

import argparse
import asyncio
import json
from enum import Enum

from pydantic import BaseModel, create_model, model_validator

from app.core.llm import complete_json
from app.render.labels import FILE

LANGUAGES = {"hi": "Hindi", "ta": "Tamil", "ml": "Malayalam", "kn": "Kannada", "te": "Telugu"}
PLACEHOLDERS = ("{page}", "{pages}")
# A one-off job where wording matters more than cost: the stronger model.
MODEL = "gemini-3.5-flash"
# Labels per call. The whole set in one call ran past Gemini's deadline.
BATCH = 20

# The sense of labels a translator can easily get wrong. Flash-Lite, without
# these, turned "Indicators of compromise" into "indicators of an agreement"
# and "Critical" into "complicated".
NOTES = {
    "Page {page} of {pages}": "page footer: the current page number, then the total number of pages",
    "Indicators of compromise": "cybersecurity: traces (IP addresses, files, hashes) showing that a "
    "system has been broken into; 'compromise' means a security breach, not an agreement",
    "Critical": "the highest security severity level",
    "High": "a security severity level",
    "Medium": "a security severity level",
    "Low": "a security severity level",
    "Informational": "the lowest security severity level: for information only",
    "Bottom line": "the heading of the one-sentence conclusion a busy reader reads first",
    "Impact": "heading: what the event means for the reader, the consequences",
    "Hash": "cybersecurity: a file's cryptographic hash value",
    "Advisory": "a formal notice telling readers what to do",
    "Notes": "a presenter's speaker notes for a slide",
    "Figure": "a number (a statistic), not a picture",
    "Key figures": "the most important numbers (statistics)",
    "Status": "whether readers must act",
}

PROMPT = """Translate these fixed labels into {language}. They are headings,
table headers, status badges and footer notes in official documents: security
advisories, executive summaries and slide decks, read by officials and staff
in India.

- Use the formal, standard terms of official {language} documents, as used by
  Indian government bodies, not literal word-for-word translations.
- Keep labels short: a heading stays a heading, a badge stays one or two words.
- Keep these as they are, in Latin letters: CVE, CVSS, IP, URL.
- Keep {{page}} and {{pages}} exactly as written; they are replaced by numbers.
- Use Western digits (0-9) only.
- Where a label has a note in brackets, the note gives its meaning; translate
  the label only, not the note.

Labels:
{labels}
"""


def _schema(ids: list[str]) -> type[BaseModel]:
    label_id = Enum("LabelId", [(i, i) for i in ids], type=str)
    item = create_model("_Label", id=(label_id, ...), text=(str, ...))

    def every_label(self):
        given = {t.id.value for t in self.translations}
        if missing := [i for i in ids if i not in given]:
            raise ValueError(f"no translation for {', '.join(missing)}; give one for every label")
        return self

    return create_model(
        "_Labels",
        translations=(list[item], ...),
        __validators__={"every_label": model_validator(mode="after")(every_label)},
    )


async def translate(lang: str, texts: list[str]) -> dict[str, str]:
    ids = [f"l{n}" for n in range(1, len(texts) + 1)]
    prompt = PROMPT.format(
        language=LANGUAGES[lang],
        labels="\n".join(
            f"[{i}] {t}" + (f"  ({NOTES[t]})" if t in NOTES else "") for i, t in zip(ids, texts)
        ),
    )
    result = await complete_json(_schema(ids), prompt, model=MODEL)
    by_id = {t.id.value: t.text.strip() for t in result.translations}
    return dict(zip(texts, (by_id[i] for i in ids)))


def _checked(lang: str, pairs: dict[str, str]) -> dict[str, str]:
    for text, translated in pairs.items():
        for p in PLACEHOLDERS:
            if (p in text) != (p in translated):
                raise SystemExit(f"{lang}: {text!r} -> {translated!r} lost or added {p}")
    return pairs


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--redo", action="store_true", help="translate every label again")
    parser.add_argument("--languages", help="comma-separated codes (default: all)")
    args = parser.parse_args()
    languages = args.languages.split(",") if args.languages else list(LANGUAGES)

    labels: dict[str, dict[str, str]] = json.loads(FILE.read_text())
    for lang in languages:
        todo = [k for k, v in labels.items() if args.redo or lang not in v]
        for start in range(0, len(todo), BATCH):
            batch = todo[start : start + BATCH]
            for text, translated in _checked(lang, await translate(lang, batch)).items():
                labels[text][lang] = translated
        # Saved per language, so a failure later keeps what is done.
        FILE.write_text(json.dumps(labels, indent=2, ensure_ascii=False) + "\n")
        print(f"{lang}: {len(todo)} labels")


if __name__ == "__main__":
    asyncio.run(main())
