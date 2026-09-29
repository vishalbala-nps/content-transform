"""Saved brand kits: create, edit, delete, and their logos.

Each kit belongs to one user, and every function here takes the user: a kit
of someone else's is "No such brand kit", exactly as one that does not exist.

A kit is chosen per job, and the job keeps a copy made at that moment
(GenerationConfig.brand_kit), so nothing here ever changes an existing job.

Logos are stored by content hash ("brand/logos/<sha256>.png") and never
deleted: a job's copy of a kit may still name a logo the kit itself has
since replaced.
"""

import hashlib
import re
import uuid
from typing import Annotated

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.db.models import BrandKitRecord, session
from app.formats.base import BrandKit, HexColour
from app.render.theme import contrast_with_white

MAX_LOGO_BYTES = 1 * 2**20

# Accent headings and white text on the accent need at least the large-text
# contrast; body text needs the normal-text contrast (WCAG 2).
MIN_PRIMARY_CONTRAST = 3.0
MIN_INK_CONTRAST = 4.5


class BrandKitError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status  # HTTP status the API layer should answer with


class BrandKitFields(BaseModel):
    """What a reviewer edits. The logo is uploaded on its own."""

    org_name: str = Field(min_length=1, max_length=80)
    primary: HexColour
    ink: HexColour = "#1a1f2b"
    # Written into CSS as a font-family name, so only characters that cannot end a string there.
    font: str | None = Field(default=None, max_length=60)
    banned_phrases: list[Annotated[str, Field(max_length=100)]] = Field(default=[], max_length=50)

    @field_validator("org_name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("the organisation name is empty")
        return v.strip()

    @field_validator("font")
    @classmethod
    def _font(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        if v and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]*", v):
            raise ValueError("a font name may only use letters, digits, spaces and hyphens")
        return v or None

    @field_validator("banned_phrases")
    @classmethod
    def _phrases(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(p.strip() for p in v if p.strip()))

    @field_validator("primary")
    @classmethod
    def _primary(cls, v: str) -> str:
        if (ratio := contrast_with_white(v)) < MIN_PRIMARY_CONTRAST:
            raise ValueError(
                f"{v} is too light to use for headings on white or behind white text "
                f"(contrast {ratio:.1f}:1, needs {MIN_PRIMARY_CONTRAST:.0f}:1); choose a darker shade"
            )
        return v.lower()

    @field_validator("ink")
    @classmethod
    def _ink(cls, v: str) -> str:
        if (ratio := contrast_with_white(v)) < MIN_INK_CONTRAST:
            raise ValueError(
                f"{v} is too light for body text on white (contrast {ratio:.1f}:1, needs "
                f"{MIN_INK_CONTRAST}:1); choose a darker shade"
            )
        return v.lower()


def _kit(record: BrandKitRecord) -> BrandKit:
    return BrandKit(kit_id=record.id, **record.kit)


def _owned(s: Session, kit_id: str, user_id: str) -> BrandKitRecord | None:
    record = s.get(BrandKitRecord, kit_id)
    return record if record and record.user_id == user_id else None


def list_kits(user_id: str) -> list[BrandKit]:
    with session() as s:
        records = s.scalars(
            select(BrandKitRecord)
            .where(BrandKitRecord.user_id == user_id)
            .order_by(BrandKitRecord.created_at)
        )
        return [_kit(r) for r in records]


def get_kit(kit_id: str, user_id: str) -> BrandKit | None:
    with session() as s:
        record = _owned(s, kit_id, user_id)
        return _kit(record) if record else None


def create_kit(user_id: str, fields: BrandKitFields) -> BrandKit:
    record = BrandKitRecord(id=uuid.uuid4().hex, user_id=user_id, kit={**fields.model_dump(), "logo": None})
    with session() as s:
        s.add(record)
        s.commit()
    return _kit(record)


def _change(kit_id: str, user_id: str, **changes) -> BrandKit:
    with session() as s:
        record = _owned(s, kit_id, user_id)
        if record is None:
            raise BrandKitError("No such brand kit.", 404)
        record.kit = {**record.kit, **changes}  # replaced, not mutated: see the Job model
        s.commit()
        return _kit(record)


def update_kit(kit_id: str, user_id: str, fields: BrandKitFields) -> BrandKit:
    return _change(kit_id, user_id, **fields.model_dump())


def delete_kit(kit_id: str, user_id: str) -> None:
    """Jobs made with the kit keep their copy, logo included."""
    with session() as s:
        record = _owned(s, kit_id, user_id)
        if record is None:
            raise BrandKitError("No such brand kit.", 404)
        s.delete(record)
        s.commit()


def _logo_extension(data: bytes) -> str:
    """By content, not by the file's name. python-pptx must be able to read
    it too, which also catches a truncated or corrupt file."""
    from pptx.parts.image import Image

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        extension = ".jpg"
    else:
        raise BrandKitError("The logo must be a PNG or JPEG image.", 422)
    try:
        width, height = Image.from_blob(data).size
    except Exception as e:
        raise BrandKitError("The logo file could not be read as an image.", 422) from e
    if not width or not height:
        raise BrandKitError("The logo image has no size.", 422)
    return extension


def set_logo(kit_id: str, user_id: str, data: bytes) -> BrandKit:
    if len(data) > MAX_LOGO_BYTES:
        raise BrandKitError(f"Logos over {MAX_LOGO_BYTES // 2**20} MB are not accepted.", 413)
    if get_kit(kit_id, user_id) is None:
        raise BrandKitError("No such brand kit.", 404)
    key = f"brand/logos/{hashlib.sha256(data).hexdigest()}{_logo_extension(data)}"
    storage.save(key, data)
    return _change(kit_id, user_id, logo=key)


def remove_logo(kit_id: str, user_id: str) -> BrandKit:
    return _change(kit_id, user_id, logo=None)
