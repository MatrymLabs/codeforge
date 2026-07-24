"""CARD: db -- persistence through the SQLAlchemy 2.0 ORM (SQLite or PostgreSQL).

Two tables, typed rows. The rest of the engine never sees SQL:
characters.py and accounts.py keep their function signatures and swap
their insides. Two backends behind one seam:

- Default: a single SQLite file (codeforge.db), absolute-pathed to the
  repo root (CODEFORGE_DB overrides the path); tests point DB_PATH at tmp.
- Production: set DATABASE_URL (a postgresql+psycopg:// URL) and the same
  ORM speaks to PostgreSQL. Schema is managed by Alembic migrations (see
  migrations/); create_all remains a zero-config convenience for SQLite.

Why an ORM for a game this size? The same reason the seed loaders
gate YAML: schemas make bad states unrepresentable, and the skill
transfers straight to PostgreSQL when the world outgrows one file.
"""

import os
from pathlib import Path

from sqlalchemy import Engine, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import Session as SqlSession

from parts.world.paths import resolved_path


def _default_db_path() -> Path:
    """Where the database lives. Absolute and anchored to the repo root
    (this file's grandparent) so the server opens the SAME file no matter
    which directory it is launched from -- a cwd-relative default once
    silently created a second, empty database when run from the wrong
    place. Override with CODEFORGE_DB for tests, containers, or a chosen
    data directory."""
    return resolved_path(
        "CODEFORGE_DB",
        Path(__file__).resolve().parent.parent.parent / "codeforge.db",  # parts/world/ -> repo root
    )


DB_PATH = _default_db_path()

_ENGINES: dict[str, Engine] = {}


class ArchiveBase(DeclarativeBase):
    pass


class CharacterRow(ArchiveBase):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(default="")
    secondary_job: Mapped[str] = mapped_column(default="")  # the equipped subjob, or "" for none
    level: Mapped[int] = mapped_column(default=1)
    xp: Mapped[int] = mapped_column(default=0)
    location: Mapped[str] = mapped_column(default="forge")
    rank: Mapped[str] = mapped_column(default="player")
    account: Mapped[str] = mapped_column(default="")
    # The sworn Order (guild-allegiance), or "". The DB column is "sworn_order" because ORDER is a
    # SQL reserved word; the Python attribute stays `order` for the rest of the code.
    order: Mapped[str] = mapped_column("sworn_order", default="")
    # Equipped gear as a JSON map {slot: prototype_label}, or "". Items are ephemeral instances, so
    # we persist the PROTOTYPE per slot and re-clone it on restore -- worn gear survives logout.
    equipped_gear: Mapped[str] = mapped_column(default="")
    # The purse: coins earned from kills, spent at shops. A simple persisted scalar.
    coins: Mapped[int] = mapped_column(default=0)
    # The current state of this seed's quest arc, or "" (still at the start / no run). Restored into
    # the quest engine on login so a story-in-progress survives a restart; ignored across seeds.
    quest_state: Mapped[str] = mapped_column(default="")
    auth_salt: Mapped[str | None] = mapped_column(default=None)  # legacy v1 char passwords
    auth_hash: Mapped[str | None] = mapped_column(default=None)


class JobProgressRow(ArchiveBase):
    """One character's progress in ONE job. A character has many of these, one per job they
    have taken up -- so changing jobs never erases a prior job's level (derive-don't-store:
    stats recompute, but the job's earned rank is a canonical fact worth keeping)."""

    __tablename__ = "job_progress"

    character_name: Mapped[str] = mapped_column(ForeignKey("characters.name"), primary_key=True)
    job_id: Mapped[str] = mapped_column(primary_key=True)
    job_level: Mapped[int] = mapped_column(default=1)
    jp: Mapped[int] = mapped_column(default=0)  # job points available in this job
    tp: Mapped[int] = mapped_column(default=0)  # training progress toward the next milestone


class AccountRow(ArchiveBase):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(primary_key=True)
    auth_salt: Mapped[str] = mapped_column()
    auth_hash: Mapped[str] = mapped_column()


def engine_url() -> str:
    """The SQLAlchemy URL in force. DATABASE_URL wins (PostgreSQL in production);
    otherwise a SQLite file at DB_PATH (the zero-config default for dev and tests)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or f"sqlite:///{DB_PATH}"


def open_archive_session() -> SqlSession:
    """A working archive session on the current backend. Engines are cached per URL.
    For SQLite the tables are created on first contact (idempotent); for PostgreSQL
    Alembic owns the schema, but create_all is a harmless checkfirst no-op if migrated."""
    url = engine_url()
    engine = _ENGINES.get(url)
    if engine is None:
        engine = create_engine(url)
        ArchiveBase.metadata.create_all(engine)  # checkfirst=True: a no-op once migrated
        _ENGINES[url] = engine
    return SqlSession(engine)


def backup_db(dest_dir: Path | None = None) -> Path:
    """Make a consistent, online copy of the SQLite database (safe while the server runs) under
    a timestamped file, and return its path. The live public demo had no recovery path; `make
    backup` files a snapshot. Refuses loud on a non-SQLite backend (use pg_dump for PostgreSQL)."""
    import sqlite3
    from datetime import UTC, datetime

    url = engine_url()
    if not url.startswith("sqlite"):
        raise RuntimeError(
            f"backup_db supports SQLite only; the backend is {url.split(':', 1)[0]}. "
            "For PostgreSQL use pg_dump (see docs/database.md)."
        )
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(f"no database to back up at {DB_PATH}")
    base = dest_dir if dest_dir is not None else Path(DB_PATH).parent / "backups"
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = base / f"{Path(DB_PATH).stem}-{stamp}.db"
    with sqlite3.connect(DB_PATH) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)  # online snapshot: consistent even under concurrent writes
    return dest
