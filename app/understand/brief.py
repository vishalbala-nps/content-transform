"""SourceDocument -> ContentBrief. The only place the source is read by a model."""

import uuid
from enum import Enum

from pydantic import BaseModel, Field, create_model

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


def _draft_schema(doc: SourceDocument) -> type[BaseModel]:
    """What the model fills: ContentBrief minus the ids, which code assigns.

    Built per document so that every `support` list may only hold this
    document's block ids, as a JSON-schema enum. The model cannot cite a block
    that does not exist or mangle an id ("/b5", "[b5]"): the provider's
    constrained decoding rules it out, and validation rejects it if not.
    """
    block_id = Enum("BlockId", [(b.id, b.id) for b in doc.blocks], type=str)
    cited = list[block_id]

    def with_support(base: type[BaseModel]) -> type[BaseModel]:
        return create_model(base.__name__, __base__=base, support=(cited, ...))

    claim = create_model(
        "_ClaimDraft",
        text=(str, Field(description="One self-contained factual statement from the source.")),
        support=(cited, Field(description="Ids of the source blocks that state this claim.")),
    )
    return create_model(
        "_BriefDraft",
        __doc__="What the model fills: ContentBrief minus the ids, which code assigns.",
        title=(str, Field(description="A short, specific title for the source.")),
        source=(SourceProfile, ...),
        tldr=(str, Field(description="Two or three sentences a busy reader could stop after.")),
        claims=(list[claim], ...),
        entities=(list[Entity], ...),
        timeline=(list[with_support(TimelineItem)], ...),
        stats=(list[with_support(Stat)], ...),
        actions=(list[with_support(Action)], ...),
        security=(SecurityDetails | None, ...),
    )


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
    draft = await complete_json(_draft_schema(doc), PROMPT.format(blocks=_render_blocks(doc)))

    # Every id is a real block (the schema allows nothing else). Empty support
    # is still possible, and is what grounding will flag later.
    def keep(ids: list[Enum]) -> Support:
        return list(dict.fromkeys(i.value for i in ids))

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
