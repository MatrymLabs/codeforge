"""CARD: db -- SQLite persistence through the SQLAlchemy 2.0 ORM.

One file on disk (codeforge.db), two tables, typed rows. The rest of
the engine never sees SQL: characters.py and accounts.py keep their
function signatures and swap their insides. The default path is
absolute and anchored to the repo root (CODEFORGE_DB overrides it);
tests point DB_PATH at a tmp file.

Why an ORM for a game this size? The same reason the seed loaders
gate YAML: schemas make bad states unrepresentable, and the skill
transfers straight to PostgreSQL when the world outgrows one file.
"""

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


def _default_db_path() -> Path:
    """Where the database lives. Absolute and anchored to the repo root
    (this file's grandparent) so the server opens the SAME file no matter
    which directory it is launched from -- a cwd-relative default once
    silently created a second, empty database when run from the wrong
    place. Override with CODEFORGE_DB for tests, containers, or a chosen
    data directory."""
    override = os.environ.get("CODEFORGE_DB")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / "codeforge.db"


DB_PATH = _default_db_path()

_ENGINES: dict[str, Engine] = {}


class Base(DeclarativeBase):
    pass


class CharacterRow(Base):
    __tablename__ = "characters"

    name: Mapped[str] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(default="")
    level: Mapped[int] = mapped_column(default=1)
    xp: Mapped[int] = mapped_column(default=0)
    location: Mapped[str] = mapped_column(default="forge")
    rank: Mapped[str] = mapped_column(default="player")
    account: Mapped[str] = mapped_column(default="")
    auth_salt: Mapped[str | None] = mapped_column(default=None)  # legacy v1 char passwords
    auth_hash: Mapped[str | None] = mapped_column(default=None)


class AccountRow(Base):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(primary_key=True)
    auth_salt: Mapped[str] = mapped_column()
    auth_hash: Mapped[str] = mapped_column()


def get_session() -> Session:
    """A working session on the current DB_PATH. Engines are cached per
    path; tables are created on first contact (idempotent)."""
    key = str(DB_PATH)
    engine = _ENGINES.get(key)
    if engine is None:
        engine = create_engine(f"sqlite:///{key}")
        Base.metadata.create_all(engine)
        _ENGINES[key] = engine
    return Session(engine)
