"""Test twin for parts/world/characters.py -- restart survival."""

import copy

import pytest

from parts.world import items, npcs
from parts.world.characters import load_character, restore_character, save_character
from parts.world.combat import award_xp
from parts.world.jobs import bind_calling
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap = copy.deepcopy(npcs.NPCS)
    items_snap = copy.deepcopy(items.ITEMS)  # gear tests clone into ITEMS; restore so nothing leaks
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    SESSIONS.clear()


def _hero() -> Session:
    s = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = s
    bind_calling(s, "vanguard")
    return s


def test_unnamed_seats_are_never_saved():
    s = Session(player_id="player1")
    save_character(s)
    assert load_character("player1") is None


def test_save_and_load_roundtrip():
    s = _hero()
    s.level, s.xp = 2, 90
    save_character(s)
    record = load_character("matrym")
    assert record == {
        "job": "vanguard",
        "secondary_job": "",
        "level": 2,
        "xp": 90,
        "location": "courtyard",
        "rank": "player",
        "account": "",
        "order": "",
        "equipped_gear": "",
        "coins": 0,
        "quest_state": "",
    }
    assert load_character("stranger") is None


def test_restore_rebuilds_the_full_sheet():
    record = {"job": "vanguard", "level": 2, "xp": 90, "location": "courtyard"}
    s = Session(player_id="matrym")
    restore_character(s, record)
    assert s.level == 2 and s.xp == 90 and s.location == "courtyard"
    assert s.stats is not None and s.stats.get("strength").base == 14
    assert s.resources["hp"].maximum == 39  # 20 + 12 + hp_gain(12) * 1
    assert s.resources["hp"].is_full


def test_restore_of_a_vanished_job_degrades_not_crashes():
    """Seeds are games: a character saved under one seed's calling, restored under a seed that
    lacks it, must become a jobless sheet (re-pick a calling), never crash the login tick."""
    s = Session(player_id="drifter")
    restore_character(
        s, {"job": "calling_from_another_seed", "level": 3, "xp": 200, "location": "courtyard"}
    )
    assert s.stats is None  # jobless, honestly degraded
    assert s.level == 3 and s.location == "courtyard"  # the rest of the sheet still restored


def test_restore_clears_transient_combat_and_gear_state():
    """A restore is a night's rest: cooldowns, statuses, and worn gear from a prior in-place
    identity must not bleed into the restored hero (equipment folds into derived stats)."""
    s = Session(player_id="matrym")
    s.equipped = {"weapon": "sword"}
    s.cooldowns = {"field_repair": 3}
    s.statuses = {"analyzed": 2}
    restore_character(s, {"job": "vanguard", "level": 1, "xp": 0, "location": "courtyard"})
    assert s.equipped == {} and s.cooldowns == {} and s.statuses == {}


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


def test_name_command_restores_a_saved_hero():
    from forge import handle_command

    veteran = _hero()
    veteran.level, veteran.xp = 2, 90
    save_character(veteran)
    SESSIONS.clear()

    fresh = Session(player_id="player1")
    SESSIONS["player1"] = fresh
    out = handle_command(fresh, "name matrym")
    assert "Welcome back" in out
    assert fresh.level == 2
    assert fresh.location == "courtyard"
    assert fresh.resources["hp"].maximum == 39


def test_equipped_gear_persists_across_a_save_and_restore():
    """Worn gear survives logout: it is stored by prototype and re-cloned + re-equipped on login."""
    from parts.world.equipment import equip
    from parts.world.items import clone, prototype_of

    s = _hero()
    clone("forge_wrench", "player")
    equip(s, "wrench")
    assert "weapon" in s.equipped
    save_character(s)

    fresh = Session(player_id="matrym", location="courtyard")
    restore_character(fresh, load_character("matrym"))
    assert "weapon" in fresh.equipped
    assert prototype_of(fresh.equipped["weapon"]) == "forge_wrench"  # same gear, fresh instance


def test_an_unknown_persisted_prototype_is_skipped_not_fatal():
    """A saved slot referencing a since-removed prototype must skip, never crash the login."""
    fresh = Session(player_id="ghost", location="courtyard")
    casefile = {
        "job": "vanguard",
        "level": 1,
        "xp": 0,
        "location": "courtyard",
        "equipped_gear": '{"weapon": "vanished_relic"}',
    }
    restore_character(fresh, casefile)  # must not raise
    assert "weapon" not in fresh.equipped  # the vanished prototype is skipped


def test_quest_progress_persists_across_a_save_and_restore():
    """A story-in-progress survives logout: the quest state saves with the character and reseeds."""
    import json

    from parts.world.quest import quest_view, reset_quests, save_state

    reset_quests()
    s = _hero()
    quest_view(s, "accept")  # advance the arc off its start
    saved = json.loads(save_state("matrym"))
    assert "accepted" in saved.values()
    save_character(s)

    reset_quests()  # simulate a server restart: in-memory quest runs are gone
    fresh = Session(player_id="matrym", location="courtyard")
    restore_character(fresh, load_character("matrym"))
    assert json.loads(save_state("matrym")) == saved  # the arc came back
