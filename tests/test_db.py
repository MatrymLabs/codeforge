"""Test twin for parts/db.py -- the schema holds the laws now."""

from parts.characters import load_character, put_record, save_character
from parts.db import CharacterRow, get_session
from parts.session import SESSIONS, Session


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
    with get_session() as db:
        assert db.get(CharacterRow, "player1") is None
