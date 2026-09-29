"""Executive summary, generated from the ContentBrief only.

Internal, not public: it may mention that indicators of compromise exist, so
it gets the full brief. Rendered twice from one payload: markdown to copy and
a one-page PDF to circulate.
"""

from pydantic import BaseModel, Field

from app.formats.base import Artifact, GenerationConfig
from app.formats.brand import theme_for
from app.formats.brief_view import brief_for_prompt
from app.formats.config_view import config_for_prompt
from app.render.labels import label
from app.render.pdf import render_pdf
from app.understand.schemas import ContentBrief

# Targets at each detail level. The schema allows the widest range of points.
MAX_WORDS = {"brief": 200, "standard": 300, "detailed": 450}
POINTS = {"brief": (2, 3), "standard": (3, 5), "detailed": (5, 7)}
MIN_POINTS, MAX_POINTS = POINTS["brief"][0], POINTS["detailed"][1]


class ExecSummary(BaseModel):
    title: str = Field(description="A plain, specific title. No hype.")
    bottom_line: str = Field(
        description="One or two sentences: what happened and why it matters to the reader. The only part some readers will see."
    )
    key_points: list[str] = Field(
        min_length=MIN_POINTS,
        max_length=MAX_POINTS,
        description="The most important facts, one sentence each, most important first.",
    )
    actions: list[str] = Field(
        description="What the reader should do or decide, taken from the brief's actions. Empty if the brief lists none."
    )
    source_note: str = Field(
        description="One line naming the source: what kind of document it is, who issued it and when, as given in the brief."
    )


PROMPT = """You are writing an executive summary: a short document its reader
can take in within two minutes and act on.

Everything you know about the subject is in the brief below. It is the only
source of truth: do not add numbers, names, dates, claims or recommendations
that are not in it.

Write a summary that:
- leads with the bottom line: what happened and why it matters
- gives {min_points} to {max_points} key points, most important first, with
  the numbers that carry the most weight exactly as the brief states them
- for a security source, states the severity and what is affected; says
  whether indicators of compromise exist but does not list them
- lists actions only if the brief gives them, in order of urgency
- attributes claims that are not official statements of fact: say who
  reported or alleged them; treat marketing language in a press release as
  the company's claim, not as fact
- has no hype, and is under {max_words} words in total

{settings}

Brief:
{brief}
"""


class ExecSummaryAdapter:
    name = "exec_summary"
    label = "Executive summary"
    public = False
    schema = ExecSummary

    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str:
        low, high = POINTS[config.detail_level]
        return PROMPT.format(
            min_points=low,
            max_points=high,
            max_words=MAX_WORDS[config.detail_level],
            settings=config_for_prompt(config),
            brief=brief_for_prompt(brief, public=self.public),
        )

    def render(self, payload: ExecSummary, config: GenerationConfig, brief: ContentBrief) -> list[Artifact]:
        lang = config.language
        sections = [f"# {payload.title}", f"**{label('Bottom line', lang)}.** {payload.bottom_line}"]
        points = "\n".join(f"- {p}" for p in payload.key_points)
        sections.append(f"## {label('Key points', lang)}\n\n{points}")
        if payload.actions:
            actions = "\n".join(f"{i}. {a}" for i, a in enumerate(payload.actions, start=1))
            sections.append(f"## {label('Actions', lang)}\n\n{actions}")
        sections.append(f"*{label('Source', lang)}: {payload.source_note}*")
        pdf = render_pdf(
            "exec_summary.html", theme_for(config), s=payload, title=payload.title, lang=config.language
        )
        return [
            Artifact(filename="exec_summary.md", media_type="text/markdown", text="\n\n".join(sections)),
            Artifact(filename="exec_summary.pdf", media_type="application/pdf", data=pdf),
        ]

    def check(self, payload: ExecSummary, artifacts: list[Artifact], config: GenerationConfig) -> list[str]:
        warnings = []
        # Set in English words; a translation's word count is not comparable.
        english = config.language == "en"
        if english and (words := len(artifacts[0].text.split())) > (limit := MAX_WORDS[config.detail_level]):
            warnings.append(f"summary is {words}/{limit} words")
        low, high = POINTS[config.detail_level]
        if not low <= (n := len(payload.key_points)) <= high:
            warnings.append(f"{n} key points; {config.detail_level} is {low}-{high}")
        return warnings


adapter = ExecSummaryAdapter()
