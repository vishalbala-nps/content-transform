"""The tables. SQLite in dev; nothing here is SQLite-specific.

A job's results are JSON columns on the row. Text artifacts live there in
full; binary ones (PDF, PPTX) are in app/core/storage.py, and the row keeps
their storage key.

Jobs and brand kits belong to one user each (`user_id`). The column is
nullable only because it was added to existing tables: rows from before
users existed have none until `python -m tools.users adopt` gives them an
owner, and until then no one sees them.
"""

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Engine, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    """One source text and the formats requested from it.

    JSON columns are replaced, never mutated in place: SQLAlchemy does not see
    in-place changes to a dict or list. Nullable ones store None as SQL NULL
    (`none_as_null`), not the JSON text `null`, so `IS NULL` works in queries.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(32), index=True)  # the owner; see the module docstring
    status: Mapped[str] = mapped_column(String(16), index=True)  # queued, running, done, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    formats: Mapped[list[str]] = mapped_column(JSON)  # registry order
    config: Mapped[dict] = mapped_column(JSON)  # GenerationConfig
    source: Mapped[dict] = mapped_column(JSON)  # SourceDocument; ingested when the job is created
    brief: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))  # ContentBrief, once built
    brief_usage: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))  # Usage of the brief's calls
    # The brief's copied wording in the job's language, by path (formats/translate.py); None for English.
    brief_translation: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)  # format name -> FormatResult
    error: Mapped[str | None] = mapped_column(Text)  # why the job failed; format errors are in outputs


class BrandKitRecord(Base):
    """A saved brand kit. Jobs never point at one: each job keeps its own copy
    (GenerationConfig.brand_kit), so editing or deleting a kit leaves old jobs
    as they were."""

    __tablename__ = "brand_kits"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(32), index=True)  # the owner; see the module docstring
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    kit: Mapped[dict] = mapped_column(JSON)  # BrandKit without kit_id: the fields and the logo's storage key


class User(Base):
    """Someone who can sign in. Created from the command line only
    (`python -m tools.users`); there is no sign-up and no admin role."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercase
    password_hash: Mapped[str] = mapped_column(String(255))  # scrypt, see app/core/users.py
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # a disabled user cannot sign in
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSession(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256
    is stored, so a copy of the database cannot be used to sign in."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@lru_cache
def engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url)


def session() -> Session:
    return Session(engine(), expire_on_commit=False)


def init_db() -> None:
    """Create missing tables, and add missing nullable columns (and their
    indexes) to existing ones.

    `create_all` never alters a table that exists. A new nullable column is
    the only change so far, and adding it needs no data migration, so this
    covers it without Alembic. Anything else (a type change, a new required
    column) needs a real migration.
    """
    eng = engine()
    Base.metadata.create_all(eng)
    existing = {t: {c["name"] for c in inspect(eng).get_columns(t)} for t in inspect(eng).get_table_names()}
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if column.name in existing.get(table.name, set()):
                    continue
                if not column.nullable:
                    raise RuntimeError(f"{table.name}.{column.name} is required and missing: needs a migration")
                kind = column.type.compile(dialect=eng.dialect)
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {kind}"))
            for index in table.indexes:
                index.create(conn, checkfirst=True)
