"""Test twin for parts/world/combat.py -- deterministic training-loop math."""

import copy
from pathlib import Path

import pytest

from parts.world import npcs
from parts.world.combat import attack, strike_power
from parts.world.jobs import bind_calling
from parts.world.seed import Npc, SeedError, load_npcs
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    # Restore in place (clear + update, never rebind): combat.py holds
    # `from parts.world.npcs import NPCS`, so rebinding npcs.NPCS would strand that alias.
    npcs_snap = copy.deepcopy(npcs.NPCS)
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    SESSIONS.clear()


def _fighter(job: str = "vanguard", location: str = "courtyard") -> Session:
    s = Session(player_id="matrym", location=location)
    SESSIONS["matrym"] = s
    bind_calling(s, job)
    return s


def test_attack_without_a_calling_is_refused():
    s = Session(player_id="matrym", location="courtyard")
    assert "no calling yet" in attack(s, "dummy")


def test_defeating_an_npc_surfaces_a_triggered_quest_line(monkeypatch):
    """Combat rides the quest hook on top: if a fallen npc completes a story beat, its line is
    appended to the defeat report (the aethryn Cinder-Wight uses this to end the Relighting)."""
    import parts.world.quest as quest_mod

    monkeypatch.setattr(
        quest_mod, "on_event", lambda session, kind, target: "[The Relighting] the cold breaks"
    )
    s = _fighter()  # courtyard: the training dummy
    out = ""
    for _ in range(10):
        out = attack(s, "dummy")
        if "collapses" in out:
            break
    assert "[The Relighting] the cold breaks" in out  # the quest hook reached the player


def test_peaceful_npcs_cannot_be_fought():
    s = _fighter(location="library")
    assert "not something you can fight" in attack(s, "librarian")


def test_damage_comes_from_strength():
    assert strike_power(_fighter("vanguard")) == 3 + 14 // 3  # 7
    SESSIONS.clear()
    assert strike_power(_fighter("scholar")) == 3 + 5 // 3  # 4


def test_strikes_wear_the_dummy_down_and_it_reassembles():
    s = _fighter()  # 7 damage vs 20 hp: 13, 6, defeat
    assert "(13/20)" in attack(s, "dummy")
    assert "(6/20)" in attack(s, "dummy")
    final = attack(s, "dummy")
    assert "reassembles" in final
    assert "You gain 30 XP." in final
    assert npcs.NPCS["training_dummy"]["hp_now"] == 20


def test_a_landed_strike_advances_the_combat_clock():
    """A basic attack is a combat action: it thaws cooldowns and ages statuses, so a player
    can trade normal blows while a cooldown recovers (not only by spending another ability)."""
    s = _fighter("engineer")
    s.cooldowns["field_repair"] = 2
    s.statuses["barrier"] = 2
    attack(s, "dummy")
    assert s.cooldowns["field_repair"] == 1  # one round passed
    assert s.statuses["barrier"] == 1


def test_a_refused_swing_does_not_advance_the_clock():
    """Only a LANDED strike counts. A swing at nothing (no target) is not a round."""
    s = _fighter("engineer")
    s.cooldowns["field_repair"] = 2
    attack(s, "nobody-here")
    assert s.cooldowns["field_repair"] == 2  # unchanged: no action was taken


def test_attack_flows_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    out = handle_command(s, "attack dummy")
    assert "You strike the training dummy" in out


def test_kill_is_an_alias_for_attack_through_the_tick():
    # kill shares attack's designation on the command spine (stage 2 slice G).
    from forge import handle_command

    s = _fighter()
    out = handle_command(s, "kill dummy")
    assert "You strike the training dummy" in out


def _spawn_hostile(
    label: str = "brawler",
    location: str = "courtyard",
    atk: int = 5,
    hp: int = 50,
    lethal: bool = False,
):
    """Place a fighting NPC in a room. Written to both aliased registries; the fixture cleans up."""
    hostile: Npc = {
        "name": f"the {label}",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": hp,
        "hp_now": hp,
        "xp": 10,
        "atk": atk,
    }
    if lethal:
        hostile["lethal"] = True
    npcs.NPCS[label] = hostile  # combat.py's NPCS alias sees this (same object, no rebinds)
    return label


def test_npc_strike_power_reads_the_atk_stat():
    from parts.world.combat import npc_strike_power

    _spawn_hostile(atk=5)
    assert npc_strike_power(npcs.NPCS["brawler"]) == 5
    assert npc_strike_power(npcs.NPCS["training_dummy"]) == 0  # passive by default


def test_a_hostile_npc_strikes_back_when_it_survives():
    s = _fighter()
    _spawn_hostile(atk=5, hp=50)
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")
    assert "strikes back for 5" in out
    assert s.resources["hp"].current == max_hp - 5  # exact, deterministic


def test_the_passive_training_dummy_never_strikes_back():
    s = _fighter()  # the dummy carries no atk stat
    max_hp = s.resources["hp"].maximum
    out = attack(s, "dummy")
    assert "strikes back" not in out
    assert s.resources["hp"].current == max_hp  # unhurt: backward compatible


def test_a_defeated_npc_does_not_counter():
    s = _fighter()
    _spawn_hostile(atk=99, hp=1)  # a huge atk, but it dies to the first blow
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")
    assert "strikes back" not in out
    assert s.resources["hp"].current == max_hp  # a corpse never counters


def test_a_fallen_player_is_restored_safely():
    s = _fighter()  # a vanguard: no Engineer reaction
    _spawn_hostile(atk=9999, hp=50)  # its counter empties the player's HP
    out = attack(s, "brawler")
    assert "Emergency Repair" not in out  # only an Engineer gets the reaction
    assert "wake restored at full health" in out
    assert s.resources["hp"].is_full  # never a broken state
    assert s.location == "courtyard"  # restored in place


def test_a_lethal_foe_kills_and_sends_the_player_home():
    from parts.world.world import START_ROOM

    s = _fighter()  # courtyard, a vanguard
    _spawn_hostile(atk=9999, hp=50, lethal=True)  # a real boss: no training-ground failsafe
    out = attack(s, "brawler")
    assert "wake where your road began" in out and "wake restored" not in out
    assert s.location == START_ROOM and s.location != "courtyard"  # sent home, not revived in place
    assert s.resources["hp"].is_full  # full health at the start room
    assert npcs.NPCS["brawler"]["hp_now"] == npcs.NPCS["brawler"]["hp"]  # the boss recovered


def test_an_engineer_emergency_repairs_out_of_a_killing_blow():
    s = _fighter("engineer")
    _spawn_hostile(atk=9999, hp=50)  # a counter that would fell anyone else
    out = attack(s, "brawler")
    assert "Emergency Repair triggers" in out  # the Engineer's reaction fired
    assert s.resources["hp"].current > 0  # pulled back from the fall
    assert "wake restored" not in out  # never needed the training-ground failsafe
    assert "emergency_repair" in s.cooldowns  # and armed its cooldown


def test_emergency_repair_fires_once_then_cools_down():
    s = _fighter("engineer")
    _spawn_hostile(atk=9999, hp=9999)  # survives every blow and keeps countering
    first = attack(s, "brawler")
    assert "Emergency Repair triggers" in first  # fires the first time
    second = attack(s, "brawler")
    assert "Emergency Repair" not in second  # on cooldown now
    assert "wake restored" in second  # so the failsafe catches this fall instead


def test_counterattack_flows_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    _spawn_hostile(atk=4, hp=50)
    out = handle_command(s, "attack brawler")
    assert "strikes back for 4" in out


def test_the_seeded_gate_boss_is_a_real_fight():
    """The spiral-ascent Coilwarden is wired for combat: reachable in play, and it hits back."""
    from parts.world.seed import SEEDS_ROOT, load_npcs

    boss = load_npcs(SEEDS_ROOT / "spiral-ascent" / "npcs.yaml")["coilwarden"]
    npcs.NPCS["coilwarden"] = boss  # its seed location is gate_chamber
    s = _fighter(location="gate_chamber")
    max_hp = s.resources["hp"].maximum
    out = attack(s, "coilwarden")
    assert "strikes back for 8" in out  # the seeded atk engages through the attack path
    assert s.resources["hp"].current == max_hp - 8  # the player took a real blow


def test_defeating_an_enemy_awards_jp():
    s = _fighter("engineer")
    out = ""
    for _ in range(10):  # strike until the dummy collapses
        out = attack(s, "dummy")
        if "reassembles" in out:
            break
    assert "JP (Engineer)" in out  # the kill line reports the JP award
    assert s.job_progress["engineer"].jp > 0


def test_defeating_an_enemy_awards_tp():
    s = _fighter("engineer")
    out = ""
    for _ in range(10):
        out = attack(s, "dummy")
        if "reassembles" in out:
            break
    assert "TP (Engineer)" in out
    assert s.job_progress["engineer"].tp > 0


# --- loot drops on defeat (object instancing consumer) --------------------------------
def test_defeating_an_npc_spawns_its_loot_drops():
    from parts.world import items

    items_snap = copy.deepcopy(items.ITEMS)
    try:
        s = _fighter(location="courtyard")
        thief = Npc(
            name="the straw thief",
            keywords=["thief"],
            location="courtyard",
            dialogue=['"..."'],
            next_line=0,
            hp=1,
            hp_now=1,
            xp=1,
            atk=0,
        )
        thief["drops"] = ["copper_key"]
        npcs.NPCS["straw_thief"] = thief
        out = attack(s, "thief")
        assert "drops to the ground" in out
        dropped = [
            iid
            for iid in items.ITEMS
            if items.prototype_of(iid) == "copper_key"
            and items.ITEMS[iid]["location"] == "room:courtyard"
        ]
        assert (
            dropped
        )  # a fresh copper_key instance on the courtyard floor (a clone, not the seed key)
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(items_snap)


def test_a_drop_of_an_unknown_prototype_is_skipped_not_a_crash():
    from parts.world import items

    items_snap = copy.deepcopy(items.ITEMS)
    try:
        s = _fighter(location="courtyard")
        gremlin = Npc(
            name="the gremlin",
            keywords=["gremlin"],
            location="courtyard",
            dialogue=['"..."'],
            next_line=0,
            hp=1,
            hp_now=1,
            xp=1,
            atk=0,
        )
        gremlin["drops"] = ["no_such_item"]
        npcs.NPCS["gremlin"] = gremlin
        out = attack(s, "gremlin")  # unknown prototype -> no drop line, no crash
        assert "drops to the ground" not in out
        assert "reassembles" in out  # the defeat still resolved cleanly
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(items_snap)


# --- weighted loot tables (Tier 1 #2) -------------------------------------------------
class _Rng:
    """A stub RNG that returns a fixed roll, so a loot draw is forced (proves the seam is
    injectable and combat stays deterministic in tests)."""

    def __init__(self, roll: int) -> None:
        self._roll = roll

    def randint(self, a: int, b: int) -> int:
        return self._roll


def _felled_foe_with(drops: list[str] | None = None, loot: dict[str, int] | None = None) -> None:
    foe = Npc(
        name="the goblin",
        keywords=["goblin"],
        location="courtyard",
        dialogue=['"..."'],
        next_line=0,
        hp=1,
        hp_now=1,
        xp=1,
        atk=0,
    )
    if drops is not None:
        foe["drops"] = drops
    if loot is not None:
        foe["loot"] = loot
    npcs.NPCS["goblin"] = foe


def test_a_loot_roll_can_force_an_item(monkeypatch):
    from parts.world import combat, items

    snap = copy.deepcopy(items.ITEMS)
    try:
        s = _fighter(location="courtyard")
        _felled_foe_with(loot={"copper_key": 1, "nothing": 5})  # copper_key is the rare outcome
        monkeypatch.setattr(combat, "_LOOT_RNG", _Rng(1))  # roll 1 -> the first entry (copper_key)
        out = attack(s, "goblin")
        assert "drops to the ground" in out
        assert any(
            items.prototype_of(i) == "copper_key" and items.ITEMS[i]["location"] == "room:courtyard"
            for i in items.ITEMS
        )
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(snap)


def test_a_loot_roll_can_come_up_nothing(monkeypatch):
    from parts.world import combat, items

    snap = copy.deepcopy(items.ITEMS)
    try:
        s = _fighter(location="courtyard")
        _felled_foe_with(loot={"copper_key": 1, "nothing": 5})
        monkeypatch.setattr(combat, "_LOOT_RNG", _Rng(6))  # roll 6 -> the last entry (nothing)
        out = attack(s, "goblin")
        assert "drops to the ground" not in out
        assert "reassembles" in out  # the defeat still resolved
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(snap)


def test_guaranteed_drops_and_a_weighted_roll_both_fire(monkeypatch):
    from parts.world import combat, items

    snap = copy.deepcopy(items.ITEMS)
    try:
        s = _fighter(location="courtyard")
        _felled_foe_with(drops=["copper_key"], loot={"copper_key": 1})  # 1 guaranteed + 1 rolled
        monkeypatch.setattr(combat, "_LOOT_RNG", _Rng(1))
        attack(s, "goblin")
        dropped = [
            i for i in items.items_in("room:courtyard") if items.prototype_of(i) == "copper_key"
        ]
        assert len(dropped) == 2  # one from drops, one from the loot roll -- distinct instances
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(snap)


def test_load_npcs_refuses_a_lethal_peaceful_foe(tmp_path):
    # a lethal foe must be combatable: hp 0 + lethal is a contradiction, refused at load
    p = tmp_path / "npcs.yaml"
    p.write_text("ghost:\n  location: courtyard\n  hp: 0\n  lethal: true\n")
    with pytest.raises(SeedError, match="lethal but has hp 0"):
        load_npcs(p)


def test_the_aethryn_boss_is_lethal():
    seeds = Path(__file__).resolve().parent.parent / "seeds"
    aethryn_npcs = load_npcs(seeds / "aethryn" / "npcs.yaml")
    assert aethryn_npcs["cinder_wight"].get("lethal") is True  # a real boss
    assert aethryn_npcs["reach_wolf"].get("lethal") is not True  # the road foe stays forgiving


def test_reward_amounts_are_flat_for_a_levelless_foe():
    """A foe without a level keeps the tutorial economy: XP, JP and TP all equal its flat xp."""
    from parts.world.combat import _reward_amounts

    s = _fighter()
    assert _reward_amounts(s, {"xp": 30}) == (30, 30, 30)


def test_reward_amounts_scale_by_the_challenge_gap_for_a_levelled_foe():
    """Fight up and a levelled foe pays; outclass it by 15+ levels and its xp drops to nothing."""
    from parts.world.combat import _reward_amounts

    s = _fighter()  # vanguard, player level 1
    s.level = 1
    assert _reward_amounts(s, {"xp": 0, "level": 3, "tier": "normal"})[0] > 0
    s.level = 30  # far past it: a gray
    assert _reward_amounts(s, {"xp": 0, "level": 3, "tier": "normal"})[0] == 0


def test_a_boss_tier_pays_ten_times_a_normal_of_the_same_level():
    from parts.world.combat import _reward_amounts

    s = _fighter()
    s.level = 5
    normal = _reward_amounts(s, {"xp": 0, "level": 8, "tier": "normal"})
    boss = _reward_amounts(s, {"xp": 0, "level": 8, "tier": "boss"})
    assert boss[0] == normal[0] * 10  # the boss multiplier is x10 the level's base


def test_land_hit_awards_the_scaled_xp_not_the_flat_field():
    """The wiring reaches the grant: a levelled foe with xp:0 still pays its curve reward."""
    from parts.world.combat import land_hit

    s = _fighter()
    s.level = 5
    npc = {"name": "the wolf", "hp": 1, "hp_now": 1, "xp": 0, "atk": 0}
    npc["level"], npc["tier"] = 8, "normal"
    before = s.xp
    defeated, _ = land_hit(s, npc, "wolf_1", 5)
    assert defeated
    assert s.xp - before == 80  # level 8 x XP_PER_LEVEL 10 x gap 1.0 -- not the flat xp:0
