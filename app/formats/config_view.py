"""The GenerationConfig as format prompts see it: one section, the same for every format.

A format's prompt says what the format is (a LinkedIn post, an advisory) and
its fixed rules. This section says who reads it, why and in what voice. It
changes emphasis and wording, never the rules: every format still uses only
the brief and attributes claims. Length comes from `detail_level`, but each
format turns that into its own targets (tweets, slides, words), so it is not
here. `language` is not here either: prompts are written in English and the
payload is translated afterwards.
"""

from app.formats.base import GenerationConfig

AUDIENCES = {
    "executive": "senior decision-makers with little time: lead with the consequences and "
    "decisions the brief states; leave out technical mechanics",
    "technical": "technical practitioners (engineers, analysts, administrators): be specific "
    "about what is affected, how and what exactly to do; technical terms need no explaining",
    "general_public": "members of the public with no specialist knowledge: use everyday words, "
    "explain any necessary term in passing, and focus on what it means for them",
    "media": "journalists who may quote or report this: lead with the news, make every fact "
    "clearly attributable, and name sources and figures precisely",
}

OBJECTIVES = {
    "inform": "help the reader understand what happened and why it matters",
    "warn": "make the reader aware of the risks the brief describes",
    "persuade": "convince the reader to act or to agree, using only the facts in the brief",
    "instruct": "tell the reader exactly what to do, in order, as far as the brief says",
    "announce": "announce the news clearly and briefly",
}

TONES = {
    "formal": "formal and measured",
    "neutral": "plain and neutral",
    "conversational": "conversational and direct, as if speaking to a colleague, while staying accurate",
    "urgent": "urgent: make clear this needs attention now, with urgency that comes only from what "
    "the brief states; never overstate severity or add deadlines",
}


def config_for_prompt(config: GenerationConfig) -> str:
    lines = [
        "Reader and purpose:",
        f"- Reader: {AUDIENCES[config.audience]}",
        f"- Purpose: {OBJECTIVES[config.objective]}",
        f"- Tone: {TONES[config.tone]}",
    ]
    if config.style and config.style.strip():
        lines.append(f"- Style requested by the user: {config.style.strip()}")
    lines += [
        "These settings change emphasis, word choice and voice only. They never override the",
        "rules above: use only what the brief states, attribute claims as described, and keep",
        "to the length limits. If the brief gives nothing for the purpose (no actions to",
        "instruct, no risk to warn about), write what the brief does support instead of",
        "inventing it.",
    ]
    return "\n".join(lines)
