"""A job's brand kit, as renderers and checks use it.

The job's config holds a copy of the kit made when the job was created
(app/formats/base.py). Renderers get a Theme built from it, never the kit;
without a kit they get the house style. The logo is stored by key, and its
bytes are loaded here before render() runs, so render() still does no I/O.
"""

import logging
import re

from pydantic import BaseModel

from app.core import storage
from app.formats.base import GenerationConfig
from app.render.theme import Theme
from app.verify.grounding import passages

log = logging.getLogger(__name__)

LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg"}


def logo_type(key: str) -> str:
    return next(t for ext, t in LOGO_TYPES.items() if key.endswith(ext))


def with_logo(config: GenerationConfig) -> tuple[GenerationConfig, list[str]]:
    """The config with the kit's logo bytes loaded, plus a warning if the file
    is missing (the files render without it). Reads storage: call it off the
    event loop."""
    kit = config.brand_kit
    if kit is None or kit.logo is None or kit.logo_data is not None:
        return config, []
    try:
        data = storage.read(kit.logo)
    except FileNotFoundError:
        log.warning("brand kit %s: logo %s is missing", kit.kit_id, kit.logo)
        return config, ["the brand kit's logo file is missing; rendered without it"]
    return config.model_copy(update={"brand_kit": kit.model_copy(update={"logo_data": data})}), []


def theme_for(config: GenerationConfig) -> Theme:
    kit = config.brand_kit
    if kit is None:
        return Theme()
    has_logo = kit.logo is not None and kit.logo_data is not None
    return Theme.branded(
        org_name=kit.org_name,
        primary=kit.primary,
        ink=kit.ink,
        font=kit.font,
        logo=kit.logo_data if has_logo else None,
        logo_type=logo_type(kit.logo) if has_logo else None,
    )


def banned_phrase_warnings(payload: BaseModel, config: GenerationConfig) -> list[str]:
    """One warning per passage that uses one of the kit's banned phrases.
    Whole words, any case: banning "AI" does not flag "maintain"."""
    kit = config.brand_kit
    phrases = [p.strip() for p in (kit.banned_phrases if kit else []) if p.strip()]
    if not phrases:
        return []
    patterns = [(p, re.compile(rf"(?<!\w){re.escape(p)}(?!\w)", re.IGNORECASE)) for p in phrases]
    return [
        f'{path} uses the banned phrase "{phrase}"'
        for path, text in passages(payload)
        for phrase, pattern in patterns
        if pattern.search(text)
    ]
