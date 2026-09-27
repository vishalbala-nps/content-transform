"""Contract 2 — ContentBrief. Frozen: see CLAUDE.md before changing.

The single intermediate representation. Every output format is generated from
this, never from the raw source. Factual items carry `support`: the Block ids
in the SourceDocument that back them, which is what grounding (S7) checks.

These models double as the schema the model fills (see understand/brief.py),
so two Gemini constraints apply:
- no `description=` on fields whose type is a model: a `$ref` sub-schema may
  not carry sibling keys. Describe the class in its docstring instead.
- no defaults: every field is required, "absent" is null or an empty list.
"""

from typing import Literal

from pydantic import BaseModel, Field

Support = list[str]


class Claim(BaseModel):
    id: str
    text: str = Field(description="One self-contained factual statement from the source.")
    support: Support = Field(description="Ids of the source blocks that state this claim.")


class Entity(BaseModel):
    name: str
    kind: Literal[
        "person", "organisation", "product", "location", "vulnerability", "threat_actor", "other"
    ]
    role: str = Field(description="One line on why this entity matters in the source.")


class TimelineItem(BaseModel):
    when: str = Field(description="The date or time as stated in the source, e.g. '2025-03-12', 'Q3 2025'.")
    event: str
    support: Support


class Stat(BaseModel):
    value: str = Field(description="The number verbatim from the source, with its unit, e.g. '42%', '9.8'.")
    label: str = Field(description="What the number measures.")
    support: Support


class Action(BaseModel):
    text: str = Field(
        description="One thing the source tells readers to do: a mitigation, directive or recommendation."
    )
    support: Support


class SourceProfile(BaseModel):
    """What kind of source this is and who it comes from, so outputs can attribute
    claims correctly ("According to a news report..." vs "The Ministry has directed...").
    Describes the source only; the brief's own claims are always written neutrally."""

    kind: Literal[
        "news_article",
        "government_memo",
        "security_advisory",
        "press_release",
        "research_report",
        "opinion",
        "internal_document",
        "other",
    ]
    origin: str | None = Field(description="Publisher, author or issuing body, as stated in the source.")
    published: str | None = Field(description="Publication or issue date, as stated in the source.")
    tone: Literal["formal", "neutral", "informal", "technical"] = Field(
        description="How the source itself is written."
    )


# --- Domain extensions -------------------------------------------------------
# Optional blocks filled only when the source is in that domain. A new domain
# is one more `<domain>: <Domain>Details | None` field on ContentBrief.


class AffectedProduct(BaseModel):
    name: str
    versions: str = Field(description="Affected versions as stated in the source, or 'unspecified'.")


class IOC(BaseModel):
    kind: Literal["ip", "domain", "url", "hash", "email", "file", "other"]
    value: str


class SecurityDetails(BaseModel):
    """Filled only when the source is about vulnerabilities, threats, attacks,
    incidents or security advisories. Mitigations go in ContentBrief.actions."""

    cve_ids: list[str]
    affected_products: list[AffectedProduct]
    severity: Literal["critical", "high", "medium", "low", "informational"] | None
    cvss_score: float | None
    iocs: list[IOC]


class ContentBrief(BaseModel):
    brief_id: str
    doc_id: str
    title: str
    source: SourceProfile
    tldr: str
    claims: list[Claim]
    entities: list[Entity]
    timeline: list[TimelineItem]
    stats: list[Stat]
    actions: list[Action]
    security: SecurityDetails | None  # null unless the source is about security
