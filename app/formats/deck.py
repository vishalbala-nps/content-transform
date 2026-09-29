"""Slide deck, generated from the ContentBrief only.

Internal, not public: a briefing deck for the organisation, so it gets the
full brief, and like the exec summary says whether indicators of compromise
exist without listing them. The model writes slide text and speaker notes;
code lays out the slides (render/pptx.py) and a markdown outline to copy.

Every limit the model must follow is stated in the prompt as well as the
schema: an Ollama model never sees the schema's descriptions.
"""

from pydantic import BaseModel, Field

from app.formats.base import Artifact, GenerationConfig
from app.formats.brand import theme_for
from app.formats.brief_view import brief_for_prompt
from app.formats.config_view import config_for_prompt
from app.render.labels import label
from app.render.pptx import DeckBuilder
from app.understand.schemas import ContentBrief

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
# Content slides at each detail level. The schema allows the widest range.
SLIDES = {"brief": (3, 4), "standard": (4, 7), "detailed": (7, 10)}
MIN_SLIDES, MAX_SLIDES = SLIDES["brief"][0], SLIDES["detailed"][1]
MIN_BULLETS, MAX_BULLETS = 2, 4
MAX_NUMBERS = 4
# Past these the text crowds the slide; check() warns.
TITLE_WORDS = 14
BULLET_WORDS = 16


class KeyNumber(BaseModel):
    value: str = Field(description="The number exactly as the brief's stats give it, with its unit.")
    label: str = Field(description="What the number measures, in a few words.")


class Slide(BaseModel):
    title: str = Field(description="The slide's takeaway as one short sentence, not a topic label.")
    bullets: list[str] = Field(
        min_length=MIN_BULLETS,
        max_length=MAX_BULLETS,
        description=f"Supporting points, at most {BULLET_WORDS} words each.",
    )
    notes: str = Field(
        description="What the presenter says on this slide: two to four sentences that add detail the bullets leave out."
    )


class Deck(BaseModel):
    title: str = Field(description="The deck's title: plain and specific.")
    subtitle: str = Field(description="One line naming the source: what kind of document, who issued it, when.")
    opening_notes: str = Field(description="What the presenter says on the title slide: why this matters, in two or three sentences.")
    key_numbers: list[KeyNumber] = Field(
        max_length=MAX_NUMBERS,
        description="The figures that matter most, taken from the brief's stats. Empty if the brief has none.",
    )
    key_numbers_notes: str = Field(
        description="What the presenter says on the key figures slide. Empty if there are no key numbers."
    )
    slides: list[Slide] = Field(min_length=MIN_SLIDES, max_length=MAX_SLIDES)


PROMPT = """You are writing a short slide deck that someone will present at a
briefing. Each slide has a title, a few bullets and speaker
notes: the words the presenter says while the slide is up.

Everything you know about the subject is in the brief below. It is the only
source of truth: do not add numbers, names, dates, claims or recommendations
that are not in it.

Write:
- title: plain and specific, no hype
- subtitle: one line naming the source: what kind of document it is, who
  issued or published it and when, as given in the brief
- opening_notes: two or three sentences for the title slide on why this
  matters to the audience
- key_numbers: up to {max_numbers} of the most important figures from the
  brief's stats, each value exactly as written there with its unit, and a
  label of a few words; empty if the brief has no stats
- key_numbers_notes: what the presenter says about those figures; empty if
  there are none
- slides: {min_slides} to {max_slides} content slides that tell the story in
  order: what happened, why it matters, the details the audience needs, and,
  if the brief gives actions, a final slide on what to do, most urgent first

For each slide:
- title: the slide's takeaway as one short sentence of at most {title_words}
  words, not a topic label ("Attackers are already exploiting the flaw", not
  "Exploitation")
- bullets: {min_bullets} to {max_bullets} points of at most {bullet_words}
  words each; short phrases are fine
- notes: two to four full sentences the presenter says, adding detail the
  bullets leave out; no stage directions

Also:
- for a security source, say how severe it is and what is affected; say
  whether indicators of compromise exist but do not list them
- attribute claims that are not official statements of fact: say who
  reported or alleged them; treat marketing language in a press release as
  the company's claim, not as fact
- keep the whole deck free of hype

{settings}

Brief:
{brief}
"""


def _outline(payload: Deck, lang: str) -> str:
    """The deck as markdown: what Copy gives, and readable without PowerPoint."""
    notes = label("Notes", lang)
    parts = [f"# {payload.title}\n\n*{payload.subtitle}*"]
    if payload.opening_notes:
        parts.append(f"> {notes}: {payload.opening_notes}")
    if payload.key_numbers:
        numbers = "\n".join(f"- **{n.value}** {n.label}" for n in payload.key_numbers)
        parts.append(f"## {label('Key figures', lang)}\n\n{numbers}")
        if payload.key_numbers_notes:
            parts.append(f"> {notes}: {payload.key_numbers_notes}")
    for slide in payload.slides:
        bullets = "\n".join(f"- {b}" for b in slide.bullets)
        parts.append(f"## {slide.title}\n\n{bullets}\n\n> {notes}: {slide.notes}")
    return "\n\n".join(parts)


class DeckAdapter:
    name = "deck"
    label = "Slide deck"
    public = False
    schema = Deck

    def prompt(self, brief: ContentBrief, config: GenerationConfig) -> str:
        return PROMPT.format(
            max_numbers=MAX_NUMBERS,
            min_slides=SLIDES[config.detail_level][0],
            max_slides=SLIDES[config.detail_level][1],
            title_words=TITLE_WORDS,
            min_bullets=MIN_BULLETS,
            max_bullets=MAX_BULLETS,
            bullet_words=BULLET_WORDS,
            settings=config_for_prompt(config),
            brief=brief_for_prompt(brief, public=self.public),
        )

    def render(self, payload: Deck, config: GenerationConfig, brief: ContentBrief) -> list[Artifact]:
        deck = DeckBuilder(title=payload.title, footer=payload.title, theme=theme_for(config))
        deck.title_slide(payload.title, payload.subtitle, payload.opening_notes)
        if payload.key_numbers:
            numbers = [(n.value, n.label) for n in payload.key_numbers]
            deck.numbers_slide(label("Key figures", config.language), numbers, payload.key_numbers_notes)
        for slide in payload.slides:
            deck.bullets_slide(slide.title, slide.bullets, slide.notes)
        return [
            Artifact(filename="deck.md", media_type="text/markdown", text=_outline(payload, config.language)),
            Artifact(filename="deck.pptx", media_type=PPTX, data=deck.to_bytes()),
        ]

    def check(self, payload: Deck, artifacts: list[Artifact], config: GenerationConfig) -> list[str]:
        warnings = []
        low, high = SLIDES[config.detail_level]
        if not low <= (n := len(payload.slides)) <= high:
            warnings.append(f"{n} content slides; {config.detail_level} is {low}-{high}")
        # Numbered as in the deck: the title slide is 1, then key figures if present.
        first = 3 if payload.key_numbers else 2
        # Word limits are set in English words; a translation's word count is
        # not comparable (Hindi writes case endings as separate words).
        words = config.language == "en"
        for number, slide in enumerate(payload.slides, start=first):
            if words and (n := len(slide.title.split())) > TITLE_WORDS:
                warnings.append(f"slide {number} title is {n}/{TITLE_WORDS} words")
            for i, bullet in enumerate(slide.bullets, start=1):
                if words and (n := len(bullet.split())) > BULLET_WORDS:
                    warnings.append(f"slide {number} bullet {i} is {n}/{BULLET_WORDS} words")
            if not slide.notes.strip():
                warnings.append(f"slide {number} has no speaker notes")
        return warnings


adapter = DeckAdapter()
