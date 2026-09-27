"""The ContentBrief as format prompts and renderers see it.

For a public format IOCs are removed, and since IOCs also surface inside claim
and action text, items that mention one are dropped as well. The same rule
applies to what the prompt shows and to the brief `render()` receives.
"""

import json

from app.understand.schemas import ContentBrief


def _ioc_free(brief: ContentBrief, texts: list[str]) -> list[str]:
    values = [i.value for i in brief.security.iocs] if brief.security else []
    return [t for t in texts if not any(v in t for v in values)]


def brief_for_prompt(brief: ContentBrief, *, public: bool) -> str:
    """The brief as JSON, without block ids, which mean nothing to a format prompt.

    The source's tone is left out too: outputs take their tone from the
    config, not from the source.
    """
    security = brief.security

    def clean(texts: list[str]) -> list[str]:
        return _ioc_free(brief, texts) if public else texts

    if security is None:
        security_view = None
    elif public:
        security_view = security.model_dump(exclude={"iocs"})
    else:
        security_view = security.model_dump()

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
            "security": security_view,
        },
        indent=2,
        ensure_ascii=False,
    )


def brief_for_render(brief: ContentBrief, *, public: bool) -> ContentBrief:
    """The brief a format's `render()` receives: whole, or for a public format without IOCs."""
    if not public or brief.security is None:
        return brief
    keep_claims = set(_ioc_free(brief, [c.text for c in brief.claims]))
    keep_actions = set(_ioc_free(brief, [a.text for a in brief.actions]))
    return brief.model_copy(
        update={
            "security": brief.security.model_copy(update={"iocs": []}),
            "claims": [c for c in brief.claims if c.text in keep_claims],
            "actions": [a for a in brief.actions if a.text in keep_actions],
        }
    )
