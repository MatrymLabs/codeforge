"""Test twin for parts/characters.py -- restart survival."""

import copy

import pytest

from parts import characters, npcs
from parts.characters import load_character, restore_character, save_character
from parts.combat import award_xp
from parts.jobs import assign_job
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS = npcs_snap
    SESSIONS.clear()


def _hero() -> Session:
    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    assign_job(s, "vanguard")
    return s


def test_unnamed_seats_are_never_saved(tmp_path):
    path = tmp_path / "characters.json"
    s = Session(player_id="player1")
    save_character(s, path)
    assert not path.exists()


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "characters.json"
    s = _hero()
    s.level, s.xp = 2, 90
    save_character(s, path)
    record = load_character("matrym", path)
    assert record == {"job": "vanguard", "level": 2, "xp": 90, "location": "courtyard"}
    assert load_character("stranger", path) is None


def test_restore_rebuilds_the_full_sheet():
    record = {"job": "vanguard", "level": 2, "xp": 90, "location": "courtyard"}
    s = Session(player_id="matrym")
    restore_character(s, record)
    assert s.level == 2 and s.xp == 90 and s.location == "courtyard"
    assert s.stats is not None and s.stats.get("strength").base == 14
    assert s.resources["hp"].maximum == 39  # 20 + 12 + hp_gain(12) * 1
    assert s.resources["hp"].is_full


def test_restored_hero_matches_a_live_grown_one():
    """The parity law: derive-on-restore must equal grow-in-play."""
    live = _hero()
    award_xp(live, 80)  # level 2 the honest way
    restored = Session(player_id="clone")
    restore_character(
        restored, {"job": "vanguard", "level": live.level, "xp": live.xp, "location": "courtyard"}
    )
    assert restored.resources["hp"].maximum == live.resources["hp"].maximum
    assert restored.resources["mp"].maximum == live.resources["mp"].maximum


def test_name_command_restores_a_saved_hero(tmp_path, monkeypatch):
    from forge import handle_command

    path = tmp_path / "characters.json"
    monkeypatch.setattr(characters, "CHARACTERS_PATH", path)
    veteran = _hero()
    veteran.level, veteran.xp = 2, 90
    save_character(veteran, path)
    SESSIONS.clear()

    fresh = Session(player_id="player1")
    SESSIONS["player1"] = fresh
    out = handle_command(fresh, "name matrym")
    assert "Welcome back" in out
    assert fresh.level == 2
    assert fresh.location == "courtyard"
    assert fresh.resources["hp"].maximum == 39
