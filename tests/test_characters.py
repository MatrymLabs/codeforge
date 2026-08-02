"""Test twin for kernel/world/characters.py -- restart survival."""

import copy

import pytest

from kernel.world import items, npcs
from kernel.world.characters import (
    load_character,
    restore_character,
    save_all,
    save_character,
)
from kernel.world.combat import award_xp
from kernel.world.jobs import bind_calling
from kernel.world.session import SESSIONS, Session


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


def test_daily_lockouts_survive_save_and_restore():
    # The endgame cap must persist: a boss claimed today stays claimed after a logout/login.
    s = _hero()
    s.lockouts = {"boss:warlord": "2026-07-29"}
    save_character(s)
    fresh = Session(player_id="matrym")
    restore_character(fresh, load_character("matrym"))
    assert fresh.lockouts == {"boss:warlord": "2026-07-29"}


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
        "guild": "",
        "guild_rank": "",
        "equipped_gear": "",
        "coins": 0,
        "quest_state": "",
        "lockouts": "",
        "allocated": "",
        "professions": "",
        "reputation": "",
        "friends": "",
    }
    assert load_character("stranger") is None


def test_profession_practice_survives_a_save_and_restore(monkeypatch):
    """A maker's trade skill is a persisted character fact: it must ride through save -> load ->
    restore. (Patch the trade registry so 'mining' is known under the test seed.)"""
    from kernel.world import professions

    monkeypatch.setattr(
        professions,
        "PROFESSIONS",
        {"mining": {"name": "Mining", "kind": "gather", "works": [], "makes": []}},
    )
    s = _hero()
    s.professions = {"mining": 5}
    save_character(s)
    fresh = Session(player_id="matrym", location="courtyard")
    restore_character(fresh, load_character("matrym"))
    assert fresh.professions == {"mining": 5}


def test_order_standing_survives_a_save_and_restore():
    """Reputation with the Orders is a persisted character fact: it must ride save -> restore.
    (Orders are code, not seed data, so 'making' is valid under any seed.)"""
    s = _hero()
    s.reputation = {"making": 300, "knowing": -50}
    save_character(s)
    fresh = Session(player_id="matrym", location="courtyard")
    restore_character(fresh, load_character("matrym"))
    assert fresh.reputation == {"making": 300, "knowing": -50}


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
    from kernel.world.equipment import equip
    from kernel.world.items import carrier, clone, prototype_of

    s = _hero()
    clone("forge_wrench", carrier("matrym"))
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

    from kernel.world.quest import quest_view, reset_quests, save_state

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


def test_affixed_gear_keeps_its_rarity_across_a_save_and_restore():
    """A rolled legendary survives logout with its name, mods, AND rarity tier."""
    from kernel.world.equipment import equip
    from kernel.world.items import ITEMS, carrier, clone

    s = _hero()
    iid = clone("forge_wrench", carrier("matrym"))
    ITEMS[iid]["name"] = "a Savage forge wrench of Ruin"  # a rolled affix instance
    ITEMS[iid]["mods"] = {"ATK": 20, "ACC": 8}
    ITEMS[iid]["rarity"] = "legendary"
    equip(s, "wrench")
    save_character(s)

    fresh = Session(player_id="matrym", location="courtyard")
    restore_character(fresh, load_character("matrym"))
    worn = ITEMS[fresh.equipped["weapon"]]
    assert worn["name"] == "a Savage forge wrench of Ruin" and worn["mods"]["ATK"] == 20
    assert worn["rarity"] == "legendary"  # the tier survives, so a client can still colour it


def test_restoring_pre_rarity_dict_gear_applies_no_rarity():
    """Gear saved before the rarity field (a dict with name/mods but no 'rarity') restores fine and
    simply carries no rarity - the backward-compatible path."""
    from kernel.world.items import ITEMS

    s = _hero()
    restore_character(
        s,
        {
            "job": "vanguard",
            "level": 1,
            "xp": 0,
            "location": "courtyard",
            "equipped_gear": '{"weapon": {"prototype": "forge_wrench", "name": "an old blade", '
            '"mods": {}}}',
        },
    )
    worn = ITEMS[s.equipped["weapon"]]
    assert worn["name"] == "an old blade"
    assert "rarity" not in worn  # nothing in the save -> no rarity applied


def test_the_legacy_bare_prototype_gear_format_still_restores():
    """An old save (equipped_gear as {slot: 'prototype'}) restores the base item, not a crash."""
    fresh = Session(player_id="matrym", location="courtyard")
    casefile = {
        "job": "vanguard",
        "level": 1,
        "xp": 0,
        "location": "courtyard",
        "equipped_gear": '{"weapon": "forge_wrench"}',  # the pre-affix-persistence format
    }
    restore_character(fresh, casefile)
    from kernel.world.items import ITEMS, prototype_of

    assert prototype_of(fresh.equipped["weapon"]) == "forge_wrench"
    assert ITEMS[fresh.equipped["weapon"]]["name"]  # a real base clone, no override


def test_save_all_persists_every_named_live_hero():
    # two named heroes + one unnamed seat, all live in SESSIONS
    ada = Session(player_id="ada", location="courtyard", named=True)
    bram = Session(player_id="bram", location="courtyard", named=True)
    stranger = Session(player_id="player9")  # still at the login desk, unnamed
    SESSIONS.update({"ada": ada, "bram": bram, "player9": stranger})
    for hero in (ada, bram):
        bind_calling(hero, "vanguard")
    saved = save_all()
    assert saved == 2  # the two named heroes, not the unnamed seat
    assert load_character("ada") is not None
    assert load_character("bram") is not None
    assert load_character("player9") is None  # an unnamed seat is never persisted


def test_save_all_on_an_empty_world_saves_nothing():
    assert save_all() == 0  # no live sessions -> a no-op, not a crash


# --- Keystone A: loose inventory survives logout ------------------------------------------------
def test_a_loose_item_survives_a_save_and_restore():
    hero = _hero()  # matrym / vanguard
    iid = items.clone("forge_wrench", items.carrier("matrym"))
    original = items.ITEMS[iid]["name"]
    save_character(hero)
    # a fresh process rebuilds ITEMS from seed: drop the live instance, then restore from storage
    items.ITEMS.pop(iid, None)
    reborn = SESSIONS["matrym"] = Session(player_id="matrym", named=True)
    restore_character(reborn, load_character("matrym"))
    names = [items.ITEMS[i]["name"] for i in items.items_in(items.carrier("matrym"))]
    assert original in names  # the loose wrench is back in the bag


def test_a_rolled_affix_survives_on_a_loose_item():
    hero = _hero()
    iid = items.clone("forge_wrench", items.carrier("matrym"))
    items.ITEMS[iid]["name"] = "a Cruel forge wrench [rare]"
    items.ITEMS[iid]["mods"] = {"ATK": 7}
    items.ITEMS[iid]["rarity"] = "rare"
    save_character(hero)
    items.ITEMS.pop(iid, None)
    reborn = SESSIONS["matrym"] = Session(player_id="matrym", named=True)
    restore_character(reborn, load_character("matrym"))
    restored = [items.ITEMS[i] for i in items.items_in(items.carrier("matrym"))]
    wrench = next(i for i in restored if i.get("rarity") == "rare")
    assert wrench["name"] == "a Cruel forge wrench [rare]" and wrench["mods"] == {"ATK": 7}


def test_two_heroes_keep_separate_bags():
    ada = SESSIONS["ada"] = Session(player_id="ada", location="courtyard", named=True)
    bram = SESSIONS["bram"] = Session(player_id="bram", location="courtyard", named=True)
    for hero in (ada, bram):
        bind_calling(hero, "vanguard")
    items.clone("forge_wrench", items.carrier("ada"))
    items.clone("rusty_lantern", items.carrier("bram"))
    save_character(ada)
    save_character(bram)
    re_ada = SESSIONS["ada"] = Session(player_id="ada", named=True)
    re_bram = SESSIONS["bram"] = Session(player_id="bram", named=True)
    restore_character(re_ada, load_character("ada"))
    restore_character(re_bram, load_character("bram"))
    ada_protos = {items.prototype_of(i) for i in items.items_in(items.carrier("ada"))}
    bram_protos = {items.prototype_of(i) for i in items.items_in(items.carrier("bram"))}
    assert "forge_wrench" in ada_protos and "rusty_lantern" not in ada_protos
    assert "rusty_lantern" in bram_protos and "forge_wrench" not in bram_protos


def test_a_reconnect_does_not_duplicate_the_bag():
    # restore twice WITHOUT dropping the live instances (a same-process reconnect): the clear
    # must keep the bag at one copy, never two.
    hero = _hero()
    items.clone("forge_wrench", items.carrier("matrym"))
    save_character(hero)
    for _ in range(2):
        reborn = SESSIONS["matrym"] = Session(player_id="matrym", named=True)
        restore_character(reborn, load_character("matrym"))
    wrenches = [
        i
        for i in items.items_in(items.carrier("matrym"))
        if items.prototype_of(i) == "forge_wrench"
    ]
    assert len(wrenches) == 1  # exactly one, not doubled by the reconnect


def test_equipped_gear_is_not_also_stored_as_a_loose_item():
    from kernel.world.loose_store import load as load_loose

    hero = _hero()
    iid = items.clone("forge_wrench", items.carrier("matrym"))
    hero.equipped["weapon"] = iid  # worn, not loose
    save_character(hero)
    bag = load_loose("matrym")
    assert bag == []  # the worn wrench persists via equipped_gear, not the loose bag (no double)
