"""Grounding: each passage of a format's output traced to the brief, and through it to the source.

A passage is one prose field of the filled payload ("slides[2].notes",
"tweets[0]"). Passages are found by walking the payload, so no format
declares anything and a new format is grounded without edits here. Values
that render() copies from the brief (the advisory's tables) are not in the
payload; they are grounded by construction.

Two checks per passage:
- One model call per format matches every passage to the brief items it
  rests on, or marks it partly supported, unsupported, or not a factual
  statement (a hashtag, a question to the reader). The items it may cite are
  an enum of this brief's item ids, as block ids are when the brief is built.
- Code lists the numbers in the passage that appear nowhere in the brief.

A passage is flagged, with reasons, when either check fails or when a brief
item it rests on cites no source block. A failed model call leaves the
number check in place and records the error; it never fails the format.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal, get_args, get_origin

from pydantic import BaseModel, Field, create_model, model_validator

from app.core.llm import LLMError, complete_json
from app.formats.brief_view import brief_for_prompt
from app.understand.schemas import ContentBrief

# Standalone numbers only: "40%", "9.8", "4,200", but not the digits in "b12" or "CVE202641877".
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)*\b")

Verdict = Literal["supported", "partial", "unsupported", "not_factual"]


class Passage(BaseModel):
    path: str  # where it sits in the payload: "slides[2].notes"
    text: str
    verdict: Verdict | None  # None when the model check failed; see Grounding.error
    items: list[str]  # brief items it rests on: "c3", "s1", "src"
    blocks: list[str]  # source blocks behind those items
    quote: str | None  # the unsupported words, verbatim; None means the whole passage
    new_numbers: list[str]  # numbers that appear nowhere in the brief
    reasons: list[str]  # why it needs review; empty when it does not


class Grounding(BaseModel):
    passages: list[Passage]
    error: str | None  # the model check failed; only the number check ran


@dataclass
class _Item:
    """One brief item a passage may rest on."""

    id: str
    text: str
    # Source blocks it cites. None for items that never carry citations (the
    # source profile, entities, security details): not a gap, just uncited.
    blocks: list[str] | None


def _items(brief: ContentBrief) -> list[_Item]:
    source = brief.source
    about = ", ".join(x for x in (source.kind.replace("_", " "), source.origin, source.published) if x)
    items = [_Item("src", f"The source is a {about}.", None), _Item("tldr", brief.tldr, None)]
    items += [_Item(c.id, c.text, c.support) for c in brief.claims]
    items += [_Item(f"s{i}", f"{s.value}: {s.label}", s.support) for i, s in enumerate(brief.stats, 1)]
    items += [_Item(f"t{i}", f"{t.when}: {t.event}", t.support) for i, t in enumerate(brief.timeline, 1)]
    items += [_Item(f"a{i}", a.text, a.support) for i, a in enumerate(brief.actions, 1)]
    items += [_Item(f"e{i}", f"{e.name} ({e.kind}): {e.role}", None) for i, e in enumerate(brief.entities, 1)]
    if sec := brief.security:
        facts = [
            f"severity {sec.severity}" if sec.severity else "",
            f"CVSS {sec.cvss_score}" if sec.cvss_score is not None else "",
            f"CVEs {', '.join(sec.cve_ids)}" if sec.cve_ids else "",
            "affected: " + "; ".join(f"{p.name} {p.versions}" for p in sec.affected_products)
            if sec.affected_products
            else "",
            f"{len(sec.iocs)} indicators of compromise" if sec.iocs else "no indicators of compromise listed",
        ]
        items.append(_Item("sec", "Security details: " + ", ".join(f for f in facts if f) + ".", None))
    return items


def _is_prose(annotation: object) -> bool:
    """A choice from a fixed set (Literal, Enum) is not prose to ground."""
    if get_origin(annotation) is Literal:
        return False
    return not (isinstance(annotation, type) and issubclass(annotation, Enum))


def passages(payload: BaseModel) -> list[tuple[str, str]]:
    """Every non-empty prose string in the payload, as (path, text), in order."""
    found: list[tuple[str, str]] = []

    def walk(value: object, path: str, annotation: object) -> None:
        if isinstance(value, BaseModel):
            for name, field in type(value).model_fields.items():
                walk(getattr(value, name), f"{path}.{name}" if path else name, field.annotation)
        elif isinstance(value, list):
            args = get_args(annotation)
            for i, item in enumerate(value):
                walk(item, f"{path}[{i}]", args[0] if args else None)
        elif isinstance(value, str) and value.strip() and _is_prose(annotation):
            found.append((path, value))

    walk(payload, "", type(payload))
    return found


PROMPT = """You are checking a piece of writing against the brief it was
written from. The brief is the only source of truth.

Each brief item starts with its id in square brackets, e.g. [c3]. Each passage
of the writing starts with its id, then where it sits in the output, e.g.
[p4] slides[1].notes.

For every passage give:
- verdict, one of:
  - supported: every factual statement in it is stated by, or follows
    directly from, the brief items you list
  - partial: some of it is supported and some is not
  - unsupported: none of its factual statements are in the brief
  - not_factual: it states no facts: a hashtag, a heading that makes no
    claim, a question or call to the reader
- items: the ids of every brief item the passage relies on; empty for
  unsupported and not_factual
- unsupported_part: for partial only, the words that are not supported,
  copied exactly as they appear in the passage; otherwise ""

Judge meaning, not wording: a paraphrase or a summary of brief items is
supported. A number, name, date, cause, consequence or recommendation that
the brief does not give is not. Saying who reported a claim ("according to
X") is supported if the brief names X as the source.

Give a verdict for every passage, in order.

Brief:
{items}

Passages:
{passages}
"""


def _judge_schema(passage_ids: list[str], item_ids: list[str]) -> type[BaseModel]:
    """Built per call, so a verdict can only name real passages and brief items."""
    passage_id = Enum("PassageId", [(p, p) for p in passage_ids], type=str)
    item_id = Enum("ItemId", [(i, i) for i in item_ids], type=str)
    verdict = create_model(
        "_PassageVerdict",
        passage=(passage_id, ...),
        verdict=(Verdict, ...),
        items=(list[item_id], Field(description="Ids of the brief items the passage relies on.")),
        unsupported_part=(str, Field(description="For partial only: the unsupported words, verbatim.")),
    )

    def every_passage(self):
        # Fails validation, so complete_json retries once with this message appended.
        given = {v.passage.value for v in self.verdicts}
        if missing := [p for p in passage_ids if p not in given]:
            raise ValueError(f"no verdict for passages {', '.join(missing)}; give one for every passage")
        return self

    return create_model(
        "_GroundingVerdicts",
        __validators__={"every_passage": model_validator(mode="after")(every_passage)},
        verdicts=(list[verdict], ...),
    )


async def ground(payload: BaseModel, brief: ContentBrief) -> Grounding:
    """Grounds against the whole brief, IOCs included, whether or not the format is public:
    this asks whether a passage is true to the source, not whether it may be published."""
    found = passages(payload)
    items = _items(brief)
    by_id = {i.id: i for i in items}
    known = set(NUMBER.findall(brief_for_prompt(brief, public=False)))

    verdicts: dict[str, BaseModel] = {}  # by path
    error = None
    if found:
        ids = [f"p{n}" for n in range(1, len(found) + 1)]
        prompt = PROMPT.format(
            items="\n".join(f"[{i.id}] {i.text}" for i in items),
            passages="\n".join(f"[{pid}] {path}: {text}" for pid, (path, text) in zip(ids, found)),
        )
        try:
            result = await complete_json(_judge_schema(ids, list(by_id)), prompt)
        except LLMError as e:
            error = f"Grounding check failed: {e}"
        else:
            by_id_given: dict[str, BaseModel] = {}
            for v in result.verdicts:
                by_id_given.setdefault(v.passage.value, v)  # the first verdict for a passage wins
            verdicts = {path: by_id_given[pid] for pid, (path, _) in zip(ids, found)}

    out = []
    for path, text in found:
        v = verdicts.get(path)
        verdict = v.verdict if v else None
        item_ids = list(dict.fromkeys(i.value for i in v.items)) if v else []
        blocks = list(dict.fromkeys(b for i in item_ids for b in by_id[i].blocks or []))
        part = v.unsupported_part.strip() if v else ""
        quote = part if verdict == "partial" and part and part in text else None
        new_numbers = list(dict.fromkeys(n for n in NUMBER.findall(text) if n not in known))

        reasons = []
        if verdict == "unsupported":
            reasons.append("not supported by the brief")
        elif verdict == "partial":
            reasons.append(f'partly unsupported: "{quote}"' if quote else "partly unsupported by the brief")
        if uncited := [i for i in item_ids if by_id[i].blocks == []]:
            reasons.append(f"rests on {', '.join(uncited)}, which cites no source block")
        if new_numbers:
            reasons.append(f"{', '.join(new_numbers)} not in the brief")

        out.append(
            Passage(
                path=path,
                text=text,
                verdict=verdict,
                items=item_ids,
                blocks=blocks,
                quote=quote,
                new_numbers=new_numbers,
                reasons=reasons,
            )
        )
    return Grounding(passages=out, error=error)
