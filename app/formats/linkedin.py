"""LinkedIn post, generated from the ContentBrief only.

`generate` takes a brief and nothing else, so the raw source cannot leak in.
S2 turns this into a registered OutputAdapter.
"""

import json

from pydantic import BaseModel, Field

from app.core.llm import complete_json
from app.understand.schemas import ContentBrief


class LinkedInPost(BaseModel):
    hook: str = Field(description="A single-line opener that makes the reader want to expand the post.")
    paragraphs: list[str] = Field(
        description="The body, one short paragraph per item. The last one is the takeaway or question."
    )
    hashtags: list[str] = Field(max_length=3, description="At most 3 hashtags, without the # sign.")


PROMPT = """You are writing a LinkedIn post for a professional audience.

Everything you know about the subject is in the brief below. It is the only
source of truth: do not add numbers, names, dates or claims that are not in it.

Write one LinkedIn post that:
- opens with a single-line hook that makes the reader want to expand the post
- is built from the tldr, the claims and the stats; if the brief lists
  actions, the most important one belongs in the post
- attributes claims to the source when it is not an official statement of
  fact: for a news article, opinion or report, say who reported it ("According
  to <origin>..."); for a government memo or advisory, name the issuing body
- uses short paragraphs of one to three sentences
- ends with one takeaway or question for the reader
- stays under 1300 characters in total
- uses at most 3 hashtags and no emoji

Brief:
{brief}
"""


def _brief_for_prompt(brief: ContentBrief) -> str:
    # Block ids mean nothing to this prompt, and IOCs do not belong in a
    # public post, so neither is sent. IOCs also surface inside claim and
    # action text, so items that mention one are dropped too.
    security = brief.security
    ioc_values = [i.value for i in security.iocs] if security else []

    def clean(texts: list[str]) -> list[str]:
        return [t for t in texts if not any(v in t for v in ioc_values)]
    return json.dumps(
        {
            "title": brief.title,
            "source": brief.source.model_dump(exclude={"tone"}),
            "tldr": brief.tldr,
            "claims": clean([c.text for c in brief.claims]),
            "stats": [{"value": s.value, "label": s.label} for s in brief.stats],
            "entities": [e.model_dump() for e in brief.entities],
            "timeline": [{"when": t.when, "event": t.event} for t in brief.timeline],
            "actions": clean([a.text for a in brief.actions]),
            "security": security.model_dump(exclude={"iocs"}) if security else None,
        },
        indent=2,
        ensure_ascii=False,
    )


def render(payload: LinkedInPost) -> str:
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in payload.hashtags)
    return "\n\n".join([payload.hook, *payload.paragraphs, *([tags] if tags else [])])


async def generate(brief: ContentBrief) -> str:
    payload = await complete_json(LinkedInPost, PROMPT.format(brief=_brief_for_prompt(brief)))
    return render(payload)
