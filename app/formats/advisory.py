"""Advisory, generated from the ContentBrief only, for any kind of source.

A formal notice to act on: a security source becomes a security advisory,
a government memo an official notice, anything else an advisory or an
information bulletin, depending on whether the brief asks readers to act.

The model writes only prose. Every exact value (CVE ids, severity, CVSS,
affected products and versions, indicators of compromise, dates, figures)
is copied into tables from the brief by render(), so a hash or a version
number is never retyped by the model. Not public: indicators of compromise
belong in an advisory, and this is the one format that lists them.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.formats.base import Artifact, GenerationConfig
from app.formats.brief_view import brief_for_prompt
from app.render.pdf import render_pdf
from app.understand.schemas import ContentBrief

MIN_DETAILS, MAX_DETAILS = 2, 5
SUMMARY_WORDS = 80


class Advisory(BaseModel):
    title: str = Field(description="A plain, specific title naming the subject. No hype.")
    status: Literal["action_required", "for_information"] = Field(
        description="action_required if the brief tells readers to do something, else for_information."
    )
    audience: str = Field(description="Who should read and act on this, in one line.")
    summary: str = Field(description="Two or three sentences: what this is about, who is affected, what to do.")
    details: list[str] = Field(
        min_length=MIN_DETAILS,
        max_length=MAX_DETAILS,
        description="What the source says, one short paragraph each, most important first.",
    )
    impact: str = Field(description="Why it matters: what is at risk or what changes for the reader, in two or three sentences.")
    actions: list[str] = Field(
        description="The brief's actions as steps, most urgent first, each one imperative sentence. Empty if the brief lists none."
    )


PROMPT = """You are writing a formal advisory: a notice that tells its readers
what has happened or been decided, what it means for them and what to do.

Everything you know about the subject is in the brief below. It is the only
source of truth: do not add numbers, names, dates, claims or recommendations
that are not in it.

The advisory already shows these, copied exactly from the brief, in tables
beside your text: {tables}. Mention them in your prose where they matter, but
do not copy long lists of them (versions, identifiers, indicators) into it.

Write:
- title: plain and specific, naming the subject
- status: "action_required" if the brief tells readers to do something,
  otherwise "for_information"
- audience: one line on who should read and act on this
- summary: two or three sentences, at most {summary_words} words: what this is
  about, who is affected and what to do
- details: {min_details} to {max_details} short paragraphs on what the source
  says, most important first
- impact: two or three sentences on why it matters to the reader
- actions: the brief's actions as steps, most urgent first, each one
  imperative sentence; empty if the brief lists none

Also:
- attribute claims that are not official statements of fact: for a news
  article, report or opinion, say who reported or alleged them; treat
  marketing language in a press release as the company's claim, not as fact;
  for a government memo or advisory, name the issuing body
- be formal and plain, with no hype

Brief:
{brief}
"""

SEVERITY_LABELS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "informational": "Informational",
}
SOURCE_KINDS = {
    "news_article": "News article",
    "government_memo": "Government memo",
    "security_advisory": "Security advisory",
    "press_release": "Press release",
    "research_report": "Research report",
    "opinion": "Opinion piece",
    "internal_document": "Internal document",
    "other": "Document",
}


def _tables(brief: ContentBrief) -> list[str]:
    """What render() will show from the brief, named for the prompt."""
    tables = []
    if brief.security:
        tables.append("severity and CVSS score, CVE ids, affected products and versions")
        if brief.security.iocs:
            tables.append("indicators of compromise")
    if brief.stats:
        tables.append("key figures")
    if brief.timeline:
        tables.append("timeline")
    return tables or ["the source's issuer and date"]


def _kind(payload: Advisory, brief: ContentBrief) -> str:
    """The document's name, shown in its header."""
    if brief.security:
        return "Security advisory"
    if brief.source.kind == "government_memo":
        return "Official notice"
    return "Advisory" if payload.status == "action_required" else "Information bulletin"


def _markdown(payload: Advisory, brief: ContentBrief, kind: str, source: str) -> str:
    """The same advisory as markdown, for Copy. Same tables, same order as the PDF."""
    lines = [f"# {kind}: {payload.title}", "", f"*{source}*", ""]
    status = "Action required" if payload.status == "action_required" else "For information"
    lines.append(f"**Status:** {status}  ")
    security = brief.security
    if security and security.severity:
        score = f" (CVSS {security.cvss_score})" if security.cvss_score is not None else ""
        lines.append(f"**Severity:** {SEVERITY_LABELS[security.severity]}{score}  ")
    if security and security.cve_ids:
        lines.append(f"**CVE:** {', '.join(security.cve_ids)}  ")
    lines += [f"**Audience:** {payload.audience}", "", "## Summary", "", payload.summary, ""]
    if security and security.affected_products:
        lines += ["## Affected products", "", "| Product | Affected versions |", "|---|---|"]
        lines += [f"| {p.name} | {p.versions} |" for p in security.affected_products]
        lines.append("")
    lines += ["## Details", "", *(d + "\n" for d in payload.details)]
    lines += ["## Impact", "", payload.impact, ""]
    if payload.actions:
        lines += ["## Actions", "", *(f"{i}. {a}" for i, a in enumerate(payload.actions, start=1)), ""]
    if brief.stats:
        lines += ["## Key figures", "", "| Figure | What it measures |", "|---|---|"]
        lines += [f"| {s.value} | {s.label} |" for s in brief.stats]
        lines.append("")
    if brief.timeline:
        lines += ["## Timeline", "", "| When | Event |", "|---|---|"]
        lines += [f"| {t.when} | {t.event} |" for t in brief.timeline]
        lines.append("")
    if security and security.iocs:
        lines += ["## Indicators of compromise", "", "| Type | Indicator |", "|---|---|"]
        lines += [f"| {i.kind} | `{i.value}` |" for i in security.iocs]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class AdvisoryAdapter:
    name = "advisory"
    label = "Advisory"
    public = False
    schema = Advisory

    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str:
        return PROMPT.format(
            tables=", ".join(_tables(brief)),
            summary_words=SUMMARY_WORDS,
            min_details=MIN_DETAILS,
            max_details=MAX_DETAILS,
            brief=brief_for_prompt(brief, public=self.public),
        )

    def render(self, payload: Advisory, config: GenerationConfig, brief: ContentBrief) -> list[Artifact]:
        kind = _kind(payload, brief)
        origin, published = brief.source.origin, brief.source.published
        source = ", ".join(x for x in (SOURCE_KINDS[brief.source.kind], origin, published) if x)
        pdf = render_pdf(
            "advisory.html",
            a=payload,
            brief=brief,
            kind=kind,
            source=source,
            severity=SEVERITY_LABELS.get(brief.security.severity) if brief.security and brief.security.severity else None,
            title=payload.title,
            lang=config.language,
        )
        return [
            Artifact(filename="advisory.md", media_type="text/markdown", text=_markdown(payload, brief, kind, source)),
            Artifact(filename="advisory.pdf", media_type="application/pdf", data=pdf),
        ]

    def check(self, payload: Advisory, artifacts: list[Artifact]) -> list[str]:
        warnings = []
        if (n := len(payload.summary.split())) > SUMMARY_WORDS:
            warnings.append(f"summary is {n}/{SUMMARY_WORDS} words")
        if payload.status == "action_required" and not payload.actions:
            warnings.append("marked action required but lists no actions")
        return warnings


adapter = AdvisoryAdapter()
