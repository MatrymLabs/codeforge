"""Test twin for parts/db.py -- the schema holds the laws now."""

from pathlib import Path

import parts.db as db
from parts.characters import load_character, put_record, save_character
from parts.db import CharacterRow, _default_db_path, open_archive_session
from parts.session import SESSIONS, Session


def test_default_db_path_is_absolute_and_repo_anchored(monkeypatch):
    """The wrong-cwd trap is closed: the default is never relative, so the
    server opens the same file from any launch directory."""
    monkeypatch.delenv("CODEFORGE_DB", raising=False)
    p = _default_db_path()
    assert p.is_absolute()
    assert p.name == "codeforge.db"
    assert p.parent == Path(db.__file__).resolve().parent.parent  # repo root


def test_codeforge_db_env_overrides_the_default(monkeypatch, tmp_path):
    target = tmp_path / "chosen.db"
    monkeypatch.setenv("CODEFORGE_DB", str(target))
    assert _default_db_path() == target


def test_tables_create_and_roundtrip():
    put_record("matrym", {"job": "vanguard", "level": 2, "xp": 90, "location": "courtyard"})
    record = load_character("matrym")
    assert record is not None
    assert record["level"] == 2
    assert record["rank"] == "player"  # column default
    assert "auth" not in record  # no auth columns set


def test_save_character_never_touches_auth_columns():
    """The merge-save law, enforced by column scope."""
    put_record(
        "matrym",
        {"job": "", "level": 1, "xp": 0, "location": "forge", "auth": {"salt": "aa", "hash": "bb"}},
    )
    hero = Session(player_id="matrym", named=True, level=5, location="cellar")
    SESSIONS["matrym"] = hero
    save_character(hero)
    SESSIONS.clear()
    record = load_character("matrym")
    assert record["level"] == 5
    assert record["auth"] == {"salt": "aa", "hash": "bb"}  # survived the save


def test_unnamed_seats_write_no_rows():
    save_character(Session(player_id="player1"))
    with open_archive_session() as db:
        assert db.get(CharacterRow, "player1") is None
