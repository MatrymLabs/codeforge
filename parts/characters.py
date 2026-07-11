"""CARD: characters -- named heroes survive the restart (SQL-backed).

Same doors as always -- load_character, save_character, put_record,
set_rank -- now opening onto a SQLite table instead of a JSON file.
Derive-don't-store is unchanged: a casefile is a handful of canonical
facts; stats and resources recompute on restore.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from parts.job_progress import load_job_progress, save_job_progress
from parts.jobs import BASE_HP, BASE_MP, bind_calling
from parts.progression import hp_gain_per_level, mp_gain_per_level
from parts.resources import Resource
from parts.session import Session

# parts.db is imported lazily inside each function that touches persistence (below), so a
# DB-free `import forge` never pays the ~400ms SQLAlchemy import (EXP-003). CharacterRow is
# needed only for annotations here, so it stays under TYPE_CHECKING.
if TYPE_CHECKING:
    from parts.db import CharacterRow


def _archive_row_to_casefile(archive_row: CharacterRow) -> dict[str, Any]:
    casefile: dict[str, Any] = {
        "job": archive_row.job,
        "secondary_job": archive_row.secondary_job,
        "level": archive_row.level,
        "xp": archive_row.xp,
        "location": archive_row.location,
        "rank": archive_row.rank,
        "account": archive_row.account,
    }
    if archive_row.auth_salt and archive_row.auth_hash:
        casefile["auth"] = {"salt": archive_row.auth_salt, "hash": archive_row.auth_hash}
    return casefile


def load_character(name: str) -> dict[str, Any] | None:
    from parts.db import CharacterRow, open_archive_session

    with open_archive_session() as db:
        archive_row = db.get(CharacterRow, name)
        return _archive_row_to_casefile(archive_row) if archive_row else None


def put_record(name: str, casefile: dict[str, Any]) -> None:
    """Write one full casefile through the single storage door."""
    from parts.db import CharacterRow, open_archive_session
    from parts.world import START_ROOM

    auth = casefile.get("auth") or {}
    with open_archive_session() as db:
        archive_row = db.get(CharacterRow, name) or CharacterRow(name=name)
        archive_row.job = casefile.get("job", "")
        archive_row.secondary_job = casefile.get("secondary_job", "")
        archive_row.level = int(casefile.get("level", 1))
        archive_row.xp = int(casefile.get("xp", 0))
        archive_row.location = casefile.get("location", START_ROOM)
        archive_row.rank = casefile.get("rank", "player")
        archive_row.account = casefile.get("account", "")
        archive_row.auth_salt = auth.get("salt")
        archive_row.auth_hash = auth.get("hash")
        db.add(archive_row)
        db.commit()


def save_character(session: Session) -> None:
    """Persist a named hero's gameplay state. Column-scoped update:
    auth fields belong to other cards and are never touched here --
    the merge-save law, now enforced by the schema itself."""
    if not session.named:
        return
    from parts.db import CharacterRow, open_archive_session

    with open_archive_session() as db:
        archive_row = db.get(CharacterRow, session.player_id) or CharacterRow(
            name=session.player_id
        )
        archive_row.job = session.job
        archive_row.secondary_job = session.secondary_job
        archive_row.level = session.level
        archive_row.xp = session.xp
        archive_row.location = session.location
        archive_row.rank = session.rank
        archive_row.account = session.account
        db.add(archive_row)
        db.commit()
    # Persist per-job progress AFTER the character row exists (the foreign key needs it).
    if session.job_progress:
        save_job_progress(session.player_id, session.job_progress.values())


def restore_character(session: Session, casefile: dict[str, Any]) -> None:
    """Rebuild the full sheet from minimal state. Resources return full:
    logging back in is a night's rest."""
    session.named = True
    session.rank = str(casefile.get("rank", "player"))
    session.account = str(casefile.get("account", ""))
    session.level = int(casefile["level"])
    session.xp = int(casefile["xp"])
    session.location = str(casefile["location"])
    session.secondary_job = str(casefile.get("secondary_job", ""))
    job = str(casefile["job"])
    if not job:
        return
    bind_calling(session, job)
    # Restore every job record this character earned; bind_calling seeded the active one.
    session.job_progress = load_job_progress(session.player_id) or session.job_progress
    assert session.stats is not None
    sta = session.stats.get("stamina").base
    mag = session.stats.get("magic").base
    grown = session.level - 1
    hp_max = BASE_HP + sta + hp_gain_per_level(sta) * grown
    mp_max = BASE_MP + mag + mp_gain_per_level(mag) * grown
    session.resources = {
        "hp": Resource(name="hp", current=hp_max, maximum=hp_max),
        "mp": Resource(name="mp", current=mp_max, maximum=mp_max),
    }


def set_rank(name: str, rank: str) -> str:
    """Host-shell grant: the bootstrap authority."""
    from parts.db import CharacterRow, open_archive_session

    with open_archive_session() as db:
        archive_row = db.get(CharacterRow, name)
        if archive_row is None:
            return f"No saved character named {name}."
        archive_row.rank = rank
        db.commit()
    return f"{name} is now rank: {rank}."
