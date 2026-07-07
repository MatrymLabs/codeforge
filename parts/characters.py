"""CARD: characters -- named heroes survive the restart.

Your name is your login (v0: no password -- LAN honesty; the future
accounts card adds real credential hashing). We persist the MINIMUM
canonical state: job, level, xp, location. Stats and resources are
DERIVED on restore from the job template and the mk1 growth formulas.
Derive, don't store: recomputable data saved twice is data that can
disagree with itself.
"""

import json
from pathlib import Path
from typing import Any

from parts.jobs import BASE_HP, BASE_MP, assign_job
from parts.progression import hp_gain_per_level, mp_gain_per_level
from parts.resources import Resource
from parts.session import Session

CHARACTERS_PATH = Path("characters.json")


def _read(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_character(session: Session, path: Path | None = None) -> None:
    """Persist a named hero. Unnamed seats (player1...) are ephemeral."""
    path = path or CHARACTERS_PATH  # resolved at CALL time, so tests can redirect it
    if not session.named:
        return
    data = _read(path)
    data[session.player_id] = {
        "job": session.job,
        "level": session.level,
        "xp": session.xp,
        "location": session.location,
    }
    path.write_text(json.dumps(data, indent=2))


def load_character(name: str, path: Path | None = None) -> dict[str, Any] | None:
    path = path or CHARACTERS_PATH
    return _read(path).get(name)


def restore_character(session: Session, record: dict[str, Any]) -> None:
    """Rebuild the full sheet from minimal state. Resources return full:
    logging back in is a night's rest."""
    session.named = True
    session.level = int(record["level"])
    session.xp = int(record["xp"])
    session.location = str(record["location"])
    job = str(record["job"])
    if not job:
        return
    assign_job(session, job)  # stats + level-1 resources
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
