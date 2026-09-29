"""Output in an Indian language: written and checked in English, then translated.

A format's payload is always written in English, grounded against the
English brief, and reviewed in English. When the job's language is not
English, the payload is translated afterwards (one call per format) and the
files are rendered from the translation, so schema limits and layout still
hold. The brief's wording that renderers copy into files (figure labels,
timeline events, dates, affected versions) is translated once per job;
exact values stay exactly as the brief has them.

Passages go to the model with ids, as for grounding, and code puts each
translation back at its path: the model cannot change the structure. Code
then checks that every number survived, that no native-script digits crept
in (every language here writes numbers in Western digits), and that no
letters from another script did. A passage with a problem is asked for once
more; what is still wrong after that is a warning, never a failure.
"""

import re
from enum import Enum

from pydantic import BaseModel, create_model, model_validator

from app.core.config import get_settings
from app.core.llm import complete_json
from app.understand.schemas import ContentBrief
from app.verify.grounding import number_value, passages, replace_at

LANGUAGE_NAMES = {"hi": "Hindi", "ta": "Tamil", "ml": "Malayalam", "kn": "Kannada", "te": "Telugu"}
SCRIPT_NAMES = {"hi": "Devanagari", "ta": "Tamil", "ml": "Malayalam", "kn": "Kannada", "te": "Telugu"}
# Below this share of letters in the language's script, a passage of a few
# words or more was not translated (a lone passage once came back as Hindi in
# Latin letters). Good translations measured 0.28 and up: names stay Latin.
MIN_SCRIPT_SHARE = 0.15

# Devanagari, Tamil, Malayalam, Kannada and Telugu digits.
NATIVE_DIGITS = re.compile("[\u0966-\u096f\u0be6-\u0bef\u0d66-\u0d6f\u0ce6-\u0cef\u0c66-\u0c6f]")

# Western digit runs, with no word boundary: Kannada and Telugu attach case
# endings straight to a number ("2026ರ", "22న"), where grounding.NUMBER's \b finds nothing.
DIGITS = re.compile(r"(?<![0-9])[0-9]+(?:[.,][0-9]+)*")

# Each language's Unicode block. A translation's letters should be in it or
# Latin (names, CVE ids); Flash-Lite once put Chinese for "bypass" into Hindi.
SCRIPTS = {"hi": (0x0900, 0x097F), "ta": (0x0B80, 0x0BFF), "ml": (0x0D00, 0x0D7F), "kn": (0x0C80, 0x0CFF), "te": (0x0C00, 0x0C7F)}

PROMPT = """Translate each passage below from English into {language}.

The passages are parts of one piece of writing, in order; each starts with
its id and where it sits, e.g. [p3] slides[1].notes. Translate each on its
own, but keep terms consistent across all of them.

- Translate the meaning faithfully. Add nothing and drop nothing: keep every
  qualifier ("at least", "about", "an estimated", "up to"), every
  attribution ("according to ...") and every hedge.
- Keep every number exactly as written, in Western digits (0-9), with its
  separators and units. Never use {language} digits.
- Keep these unchanged, in Latin letters: CVE ids, version numbers, product
  and software names, organisation names and their abbreviations (for
  example CERT-In, CVSS, VPN), URLs, email addresses, file names and hashes.
- Match the tone of the English: formal stays formal, conversational stays
  conversational. Use the vocabulary of official {language} writing in
  India, not word-for-word renderings.
- Security terms keep their security meaning: to "compromise" a system is to
  break into it (never an agreement or settlement), an "exploit" is an
  attack, an "indicator" is a trace an attack leaves.
- Write {language} in {script} script, never transliterated into Latin
  letters. Only the names, ids and abbreviations above stay in Latin letters.
  Use no other script.
- Keep each passage about as long as the English; shorter is fine. Some are
  posts with character limits.
- A hashtag (a single word or phrase with no spaces) becomes one hashtag in
  {language}, still without spaces and without the # sign.

Passages:
{passages}
"""


def _schema(ids: list[str]) -> type[BaseModel]:
    """Built per call, so a translation can only name real passages."""
    passage_id = Enum("PassageId", [(i, i) for i in ids], type=str)
    item = create_model("_Translation", id=(passage_id, ...), text=(str, ...))

    def every_passage(self):
        # Fails validation, so complete_json retries once with this appended.
        given = {t.id.value for t in self.translations}
        if missing := [i for i in ids if i not in given]:
            raise ValueError(f"no translation for {', '.join(missing)}; translate every passage")
        return self

    return create_model(
        "_Translations",
        translations=(list[item], ...),
        __validators__={"every_passage": model_validator(mode="after")(every_passage)},
    )


def _foreign_letters(text: str, language: str) -> str:
    """Letters in neither the language's script nor Latin."""
    low, high = SCRIPTS[language]
    return "".join(c for c in text if c.isalpha() and not (low <= ord(c) <= high or ord(c) < 0x0250))


def _problems(english: str, translated: str, language: str) -> list[str]:
    """What is wrong with one translated passage, in words the model can act on."""
    name = LANGUAGE_NAMES[language]
    problems = []
    kept = {number_value(n) for n in DIGITS.findall(translated)}
    if lost := [n for n in dict.fromkeys(DIGITS.findall(english)) if number_value(n) not in kept]:
        problems.append(f"{', '.join(lost)} missing from the {name} translation")
    if NATIVE_DIGITS.search(translated):
        problems.append(f"the {name} translation uses {name} digits, not 0-9")
    if foreign := _foreign_letters(translated, language):
        problems.append(f"the {name} translation has letters from another script ({foreign})")
    low, high = SCRIPTS[language]
    letters = [c for c in translated if c.isalpha()]
    share = sum(low <= ord(c) <= high for c in letters) / max(1, len(letters))
    if len(english.split()) >= 4 and share < MIN_SCRIPT_SHARE:
        problems.append(f"not written in {SCRIPT_NAMES[language]} script")
    return problems


async def _ask(
    texts: dict[str, str], language: str, notes: dict[str, list[str]], model: str | None = None
) -> dict[str, str]:
    keys = list(texts)
    ids = [f"p{n}" for n in range(1, len(keys) + 1)]

    def line(i: str, k: str) -> str:
        fix = f"\n  (Your previous translation of this was wrong: {'; '.join(notes[k])}. Fix that.)" if k in notes else ""
        return f"[{i}] {k}: {texts[k]}{fix}"

    prompt = PROMPT.format(
        language=LANGUAGE_NAMES[language],
        script=SCRIPT_NAMES[language],
        passages="\n".join(line(i, k) for i, k in zip(ids, keys)),
    )
    result = await complete_json(_schema(ids), prompt, model)
    by_id: dict[str, str] = {}
    for t in result.translations:
        by_id.setdefault(t.id.value, t.text.strip())  # the first translation of a passage wins
    # An empty translation keeps the English rather than blanking a field.
    return {k: by_id[i] or texts[k] for i, k in zip(ids, keys)}


async def translate_texts(texts: dict[str, str], language: str) -> dict[str, str]:
    """English texts by key (a payload path) -> the same keys in `language`.

    Passages with a problem code can see (a lost number, native digits,
    another script, Latin transliteration) are sent once more on their own,
    with the problem named, to the stronger model: Flash-Lite repeated its
    own mistake when asked again. A second attempt that is no better is not
    used; what remains is left to translation_warnings.
    """
    if not texts:
        return {}
    out = await _ask(texts, language, {})
    notes = {k: p for k in texts if (p := _problems(texts[k], out[k], language))}
    if notes:
        again = await _ask({k: texts[k] for k in notes}, language, notes, get_settings().llm_strong_model)
        for k, text in again.items():
            if len(_problems(texts[k], text, language)) < len(notes[k]):
                out[k] = text
    return out


async def translate_payload(payload: BaseModel, language: str) -> BaseModel:
    """The payload with every passage translated; everything else (choices
    such as an advisory's status) untouched."""
    translated = await translate_texts(dict(passages(payload)), language)
    for path, text in translated.items():
        payload = replace_at(payload, path, text)
    return payload


def translation_warnings(english: BaseModel, translation: BaseModel, language: str) -> list[str]:
    """What is still wrong with the shipped translation, passage by passage."""
    shipped = dict(passages(translation))
    return [
        f"{path}: {problem}"
        for path, text in passages(english)
        for problem in _problems(text, shipped.get(path, ""), language)
    ]


# --- The brief's wording that renderers copy into files ------------------------


def brief_texts(brief: ContentBrief) -> dict[str, str]:
    """The prose renderers copy from the brief, by path. Values (figures,
    CVE ids, product names, hashes) are not in here and are never translated."""
    texts = {f"stats[{i}].label": s.label for i, s in enumerate(brief.stats)}
    for i, t in enumerate(brief.timeline):
        texts[f"timeline[{i}].when"] = t.when  # month names; digits stay
        texts[f"timeline[{i}].event"] = t.event
    if brief.security:
        for i, p in enumerate(brief.security.affected_products):
            texts[f"security.affected_products[{i}].versions"] = p.versions  # "all versions before 2.1.3"
    if brief.source.published:
        texts["source.published"] = brief.source.published
    return texts


async def translate_brief(brief: ContentBrief, language: str) -> dict[str, str]:
    return await translate_texts(brief_texts(brief), language)


def with_brief_translation(brief: ContentBrief, translated: dict[str, str] | None) -> ContentBrief:
    """The brief with its copied wording in the output language. Paths that no
    longer exist are skipped, so a stale translation cannot break a render."""
    if not translated:
        return brief
    current = brief_texts(brief)
    for path, text in translated.items():
        if path in current:
            brief = replace_at(brief, path, text)
    return brief
