"""The ContentBrief as format prompts see it."""

import json

from app.understand.schemas import ContentBrief


def brief_for_prompt(brief: ContentBrief, *, public: bool) -> str:
    """The brief as JSON, without block ids, which mean nothing to a format prompt.

    The source's tone is left out too: outputs take their tone from the
    config, not from the source. For a public format IOCs are removed, and
    since IOCs also surface inside claim and action text, items that mention
    one are dropped as well.
    """
    security = brief.security
    ioc_values = [i.value for i in security.iocs] if security and public else []

    def clean(texts: list[str]) -> list[str]:
        return [t for t in texts if not any(v in t for v in ioc_values)]

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
