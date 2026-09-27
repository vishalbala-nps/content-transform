"""SourceDocument -> ContentBrief. The only place the source is read by a model."""

import uuid

from pydantic import BaseModel, Field

from app.core.llm import complete_json
from app.ingest.base import SourceDocument
from app.understand.schemas import (
    Action,
    Claim,
    ContentBrief,
    Entity,
    SecurityDetails,
    SourceProfile,
    Stat,
    Support,
    TimelineItem,
)


class _ClaimDraft(BaseModel):
    text: str = Field(description="One self-contained factual statement from the source.")
    support: Support = Field(description="Ids of the source blocks that state this claim.")


class _BriefDraft(BaseModel):
    """What the model fills: ContentBrief minus the ids, which code assigns."""

    title: str = Field(description="A short, specific title for the source.")
    source: SourceProfile
    tldr: str = Field(description="Two or three sentences a busy reader could stop after.")
    claims: list[_ClaimDraft]
    entities: list[Entity]
    timeline: list[TimelineItem]
    stats: list[Stat]
    actions: list[Action]
    security: SecurityDetails | None


PROMPT = """You are analysing a source document so that several communication
artefacts (social posts, summaries, advisories, slides) can later be written
from your analysis alone. Nobody downstream will see the source, so capture
everything that matters and nothing that is not in it.

The source is split into blocks. Each block starts with its id in square
brackets, e.g. [b3].

Rules:
- Only record what the source states. Do not infer, estimate or add outside
  knowledge. If the source does not give a value, use null or an empty list.
- source: describe the document itself. `origin` is who wrote or issued it.
  `published` is the date the document itself carries (a byline, header or
  issue date), never the date of an event it describes; null if it has none.
  `tone` is how the source is written.
- Write the title, tldr, claims and everything else in plain, neutral language
  whatever the source's tone: no slang, hype, jokes or opinion carried over.
  If the source gives an opinion or allegation, record it as one, attributed
  ("X says...", "the article alleges...").
- claims: the 5-15 most important factual statements, each self-contained
  (no "it" or "this" referring to another claim). Cite every block id that
  states the claim in `support`. Use only ids that appear below.
- stats: numbers copied verbatim, with units. timeline: dated events only.
- actions: what the source tells readers to do (mitigations, directives,
  recommendations), with supporting block ids. Empty if it asks nothing.
- security: fill only if the source is about vulnerabilities, threats,
  attacks, incidents or security advisories. Otherwise null.

Source:
{blocks}
"""


def _render_blocks(doc: SourceDocument) -> str:
    return "\n\n".join(f"[{b.id}] {b.text}" for b in doc.blocks)


async def build_brief(doc: SourceDocument) -> ContentBrief:
    draft = await complete_json(_BriefDraft, PROMPT.format(blocks=_render_blocks(doc)))

    # The model may cite ids that do not exist. Drop them rather than fail:
    # a claim with empty support is exactly what grounding will flag later.
    known = {b.id for b in doc.blocks}

    def keep(ids: Support) -> Support:
        return [i for i in ids if i in known]

    return ContentBrief(
        brief_id="brief_" + uuid.uuid4().hex[:12],
        doc_id=doc.doc_id,
        title=draft.title,
        source=draft.source,
        tldr=draft.tldr,
        claims=[
            Claim(id=f"c{i}", text=c.text, support=keep(c.support))
            for i, c in enumerate(draft.claims, start=1)
        ],
        entities=draft.entities,
        timeline=[t.model_copy(update={"support": keep(t.support)}) for t in draft.timeline],
        stats=[s.model_copy(update={"support": keep(s.support)}) for s in draft.stats],
        actions=[a.model_copy(update={"support": keep(a.support)}) for a in draft.actions],
        security=draft.security,
    )
