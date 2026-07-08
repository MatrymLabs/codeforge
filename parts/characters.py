"""CARD: characters -- named heroes survive the restart (SQL-backed).

Same doors as always -- load_character, save_character, put_record,
set_rank -- now opening onto a SQLite table instead of a JSON file.
Derive-don't-store is unchanged: a record is a handful of canonical
facts; stats and resources recompute on restore.
"""

from typing import Any

from parts.db import CharacterRow, get_session
from parts.jobs import BASE_HP, BASE_MP, assign_job
from parts.progression import hp_gain_per_level, mp_gain_per_level
from parts.resources import Resource
from parts.session import Session


def _row_to_record(row: CharacterRow) -> dict[str, Any]:
    record: dict[str, Any] = {
        "job": row.job,
        "level": row.level,
        "xp": row.xp,
        "location": row.location,
        "rank": row.rank,
        "account": row.account,
    }
    if row.auth_salt and row.auth_hash:
        record["auth"] = {"salt": row.auth_salt, "hash": row.auth_hash}
    return record


def load_character(name: str) -> dict[str, Any] | None:
    with get_session() as db:
        row = db.get(CharacterRow, name)
        return _row_to_record(row) if row else None


def put_record(name: str, record: dict[str, Any]) -> None:
    """Write one full record through the single storage door."""
    auth = record.get("auth") or {}
    with get_session() as db:
        row = db.get(CharacterRow, name) or CharacterRow(name=name)
        row.job = record.get("job", "")
        row.level = int(record.get("level", 1))
        row.xp = int(record.get("xp", 0))
        row.location = record.get("location", "forge")
        row.rank = record.get("rank", "player")
        row.account = record.get("account", "")
        row.auth_salt = auth.get("salt")
        row.auth_hash = auth.get("hash")
        db.add(row)
        db.commit()


def save_character(session: Session) -> None:
    """Persist a named hero's gameplay state. Column-scoped update:
    auth fields belong to other cards and are never touched here --
    the merge-save law, now enforced by the schema itself."""
    if not session.named:
        return
    with get_session() as db:
        row = db.get(CharacterRow, session.player_id) or CharacterRow(name=session.player_id)
        row.job = session.job
        row.level = session.level
        row.xp = session.xp
        row.location = session.location
        row.rank = session.rank
        row.account = session.account
        db.add(row)
        db.commit()


def restore_character(session: Session, record: dict[str, Any]) -> None:
    """Rebuild the full sheet from minimal state. Resources return full:
    logging back in is a night's rest."""
    session.named = True
    session.rank = str(record.get("rank", "player"))
    session.account = str(record.get("account", ""))
    session.level = int(record["level"])
    session.xp = int(record["xp"])
    session.location = str(record["location"])
    job = str(record["job"])
    if not job:
        return
    assign_job(session, job)
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
    with get_session() as db:
        row = db.get(CharacterRow, name)
        if row is None:
            return f"No saved character named {name}."
        row.rank = rank
        db.commit()
    return f"{name} is now rank: {rank}."
