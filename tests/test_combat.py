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
    npcs.reindex_npcs()
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
    npcs.reindex_npcs()
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
    npcs.reindex_npcs()
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
    assert aethryn_npcs["netharions_throne_guardian"].get("lethal") is True  # a real boss
    assert aethryn_npcs["veridia_warden"].get("lethal") is not True  # a townsfolk is not lethal


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


def test_a_sworn_order_raises_strike_power():
    """The Warcraft Order's ATK perk is real in a fight, not just on the sheet."""
    from parts.world.combat import strike_power

    s = _fighter("vanguard")
    s.named = True
    base = strike_power(s)
    s.order = "warcraft"  # ATK +4
    assert strike_power(s) == base + 4


def test_def_from_an_order_mitigates_a_blow_and_a_landed_hit_always_stings():
    """DEF (here from the Making Order) turns a blow, but a hit never drops below 1 damage."""
    from parts.world.combat import _resolve_npc_blow

    s = _fighter("vanguard")
    s.named = True
    brute = {"name": "a brute", "atk": 6, "hp": 10, "hp_now": 10}
    before = s.resources["hp"].current
    _resolve_npc_blow(s, brute, "hits")
    assert s.resources["hp"].current == before - 6  # no order: full damage

    s.resources["hp"] = s.resources["hp"].heal(999)
    s.order = "making"  # DEF +4
    before = s.resources["hp"].current
    _resolve_npc_blow(s, brute, "hits")
    assert s.resources["hp"].current == before - 2  # 6 - 4 mitigated

    s.resources["hp"] = s.resources["hp"].heal(999)
    gnat = {"name": "a gnat", "atk": 2, "hp": 5, "hp_now": 5}
    before = s.resources["hp"].current
    _resolve_npc_blow(s, gnat, "nips")
    assert s.resources["hp"].current == before - 1  # 2 - 4 floored at 1


def test_coin_reward_scales_with_level_and_tier():
    from parts.world.combat import _coin_reward

    assert _coin_reward({"level": 10, "tier": "normal", "xp": 0}) == 10
    assert _coin_reward({"level": 10, "tier": "elite", "xp": 0}) == 30  # elite x3
    assert _coin_reward({"level": 10, "tier": "boss", "xp": 0}) == 100  # boss x10
    assert _coin_reward({"xp": 50}) == 5  # a levelless foe pays a token purse (xp // 10)


def test_a_kill_fills_the_purse():
    from parts.world.combat import attack

    s = _fighter()  # the courtyard training dummy
    before = s.coins
    out = ""
    for _ in range(12):
        out = attack(s, "dummy")
        if "collapses" in out:
            break
    assert "purse:" in out  # the reward line shows the (denominated) purse
    assert s.coins > before  # a kill fills the purse


def test_wallet_reports_the_purse_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    s.coins = 250
    assert "2 sparks, 50 cinders" in handle_command(s, "wallet")  # 250 base coins, denominated


def test_a_levelled_equippable_drop_rolls_and_stores_a_rarity():
    """A levelled foe's gear drop runs the affix factory, which stamps a rarity tier onto the
    instance so a client can colour it (and it survives logout)."""
    from parts.world import combat, items

    session = Session(player_id="ada", location="loot_rarity_test_room")
    line = combat._spawn_loot(session, "forge_wrench", level=8)  # equippable + levelled -> rolls
    assert line  # a drop line was announced
    dropped = items.items_in("room:loot_rarity_test_room")  # clone() tags the room location
    assert dropped
    iid = dropped[0]
    try:
        assert items.ITEMS[iid]["rarity"] in {
            "common",
            "uncommon",
            "rare",
            "epic",
            "legendary",
        }
    finally:
        items.ITEMS.pop(iid, None)  # do not leak the instance (conftest clears SESSIONS, not ITEMS)


def test_a_deployed_barrier_turns_half_an_npc_blow():
    """The Engineer's Deploy Barrier now actually defends: while it holds, an NPC blow lands for
    half (floored at 1). It used to cost Power Cells and do nothing."""
    from parts.world.combat import open_strike

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=12)]
    full = s.resources["hp"].maximum

    open_strike(s, npc)  # unwarded: the full blow lands
    unwarded_loss = full - s.resources["hp"].current
    assert unwarded_loss > 1

    s.resources["hp"] = s.resources["hp"].heal(full)  # top back up
    s.statuses["barrier"] = 3
    line = open_strike(s, npc)  # warded: half the blow
    warded_loss = full - s.resources["hp"].current
    assert warded_loss == max(1, unwarded_loss // 2)  # the barrier really reduced the damage
    assert "barrier turns half" in line


def test_an_analyzed_foe_takes_bonus_damage():
    """Diagnostic Scan now matters: while 'analyzed' holds, a strike hits the revealed weak point
    for +50%. It used to set a status combat never read."""
    from parts.world.combat import attack, strike_power

    s = _fighter()
    base = strike_power(s)
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=500)]  # atk 0 so no counter muddies the hp

    attack(s, "brute")  # unanalyzed
    assert npc["hp"] - npc["hp_now"] == base

    s.statuses["analyzed"] = 3
    out = attack(s, "brute")  # analyzed: +50%
    analyzed_loss = (npc["hp"] - npc["hp_now"]) - base
    assert analyzed_loss == base + base // 2
    assert "weak point" in out


def test_a_brand_burns_a_foe_over_the_world_beats_but_never_kills():
    """A burn saps HP each world beat, floored at 1 (it wears a foe down; you land the last blow),
    and burns out after its ticks."""
    from parts.world.combat import apply_burn, tick_burns

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=10)]
    apply_burn(npc, damage=4, ticks=3)

    assert "smoulders for 4" in tick_burns(s) and npc["hp_now"] == 6  # beat 1
    tick_burns(s)  # beat 2 -> 2
    tick_burns(s)  # beat 3 -> floored at 1, burn spent
    assert npc["hp_now"] == 1  # a burn never fells a foe
    assert "burn" not in npc  # burned out after its ticks
    assert tick_burns(s) == ""  # nothing is burning now


def test_a_burn_never_revives_a_downed_foe():
    """A foe at 0 HP (mid-defeat) is skipped by the burn tick: no burning a corpse back to 1."""
    from parts.world.combat import apply_burn, tick_burns

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("husk", atk=0, hp=10)]
    npc["hp_now"] = 0
    apply_burn(npc, damage=4)
    assert tick_burns(s) == ""  # a downed foe does not smoulder
    assert npc["hp_now"] == 0  # and is not revived to the floor of 1


def _fire_wight(atk: int = 10, hp: int = 100):
    """A foe whose blows carry the FIR element, for testing the resistance scaling."""
    npc = npcs.NPCS[_spawn_hostile("wight", atk=atk, hp=hp)]
    npc["attack_element"] = "FIR"
    return npc


@pytest.mark.parametrize(
    "level, expected_loss, note",
    [
        ("Weak", 15, "finds a weakness"),  # +50%
        ("Normal", 10, ""),  # unchanged: an element the calling neither resists nor fears
        ("Resist", 5, "shrug off"),  # halved
        ("Immune", 0, "immune to flame"),  # nullified
    ],
)
def test_a_typed_blow_is_scaled_by_the_players_resistance(monkeypatch, level, expected_loss, note):
    """A foe's attack_element meets the player's job resistance: the displayed grid is real in a
    fight. An ungeared vanguard takes atk 10 -> the resistance level scales it."""
    from parts.world.combat import _resolve_npc_blow
    from parts.world.jobs import JOBS

    monkeypatch.setitem(JOBS["vanguard"]["resistances"], "FIR", level)
    s = _fighter("vanguard")
    npc = _fire_wight(atk=10)
    full = s.resources["hp"].maximum
    line = _resolve_npc_blow(s, npc, "hits")
    assert full - s.resources["hp"].current == expected_loss
    assert note in line


def test_an_untyped_blow_ignores_resistance(monkeypatch):
    """A foe with no attack_element deals physical damage no resistance touches (backward-compat:
    every existing foe fights exactly as before)."""
    from parts.world.combat import _resolve_npc_blow
    from parts.world.jobs import JOBS

    monkeypatch.setitem(JOBS["vanguard"]["resistances"], "FIR", "Immune")  # would nullify FIR
    s = _fighter("vanguard")
    npc = npcs.NPCS[_spawn_hostile("brute", atk=10, hp=100)]  # untyped: no attack_element
    full = s.resources["hp"].maximum
    _resolve_npc_blow(s, npc, "hits")
    assert full - s.resources["hp"].current == 10  # the full blow: the element gate never fired


def test_an_absorbed_element_heals_instead_of_harming(monkeypatch):
    """Absorb is the deepest resistance: the element mends the player rather than wounding them."""
    from parts.world.combat import _resolve_npc_blow
    from parts.world.jobs import JOBS

    monkeypatch.setitem(JOBS["vanguard"]["resistances"], "FIR", "Absorb")
    s = _fighter("vanguard")
    npc = _fire_wight(atk=10)
    s.resources["hp"] = s.resources["hp"].damage(20)  # wounded, so a heal is visible
    before = s.resources["hp"].current
    line = _resolve_npc_blow(s, npc, "hits")
    assert s.resources["hp"].current == before + 10  # the flame mended instead of harmed
    assert "drink in the flame" in line


@pytest.mark.parametrize(
    "grid, element, expected",
    [
        (None, "FIR", 10),  # no grid: full damage
        ({"FIR": "Weak"}, "FIR", 15),  # +50%
        ({"FIR": "Resist"}, "FIR", 5),  # halved
        ({"FIR": "Immune"}, "FIR", 0),  # nullified
        ({"FIR": "Absorb"}, "FIR", 0),  # a player's blow can't heal a foe: Absorb reads as Immune
        ({"ICE": "Weak"}, "FIR", 10),  # a mismatched element is unaffected
        ({"FIR": "Immune"}, None, 10),  # an untyped move ignores the grid entirely
    ],
)
def test_typed_hit_scales_outgoing_damage_by_the_foes_resistance(grid, element, expected):
    from parts.world.combat import typed_hit

    npc = npcs.NPCS[_spawn_hostile("golem", atk=0, hp=500)]
    if grid is not None:
        npc["resistances"] = grid
    dmg, _note = typed_hit(npc, element, 10)
    assert dmg == expected


def test_foe_resistance_defaults_to_normal_without_a_grid():
    from parts.world.combat import foe_resistance

    npc = npcs.NPCS[_spawn_hostile("golem", atk=0, hp=10)]
    assert foe_resistance(npc, "FIR") == "Normal"  # no grid at all
    npc["resistances"] = {"ICE": "Weak"}
    assert foe_resistance(npc, "FIR") == "Normal"  # a grid that omits the code
    assert foe_resistance(npc, "ICE") == "Weak"


# --- examine: the elemental profile is learnable, not guesswork ---------------------------------


def test_elemental_profile_reads_a_typed_foe():
    from parts.world.combat import elemental_profile

    npc = npcs.NPCS[_spawn_hostile("wight", atk=5, hp=50)]
    npc["attack_element"] = "FIR"
    npc["resistances"] = {"FIR": "Immune", "ICE": "Weak", "LGT": "Normal"}
    profile = elemental_profile(npc)
    assert "strike with flame" in profile
    assert "Weak to frost" in profile
    assert "Immune to flame" in profile
    assert "lightning" not in profile  # a Normal entry is not a weakness or resistance: omitted


def test_elemental_profile_is_empty_for_a_plain_foe():
    from parts.world.combat import elemental_profile

    npc = npcs.NPCS[_spawn_hostile("brute", atk=5, hp=50)]
    assert elemental_profile(npc) == ""  # untyped and resists nothing: nothing to learn


def test_examine_reveals_a_foes_nature_and_reaches_the_tick():
    from forge import handle_command

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("wight", atk=5, hp=50)]
    npc["attack_element"] = "FIR"
    npc["resistances"] = {"ICE": "Weak"}
    out = handle_command(s, "examine wight")  # reachable through the engine tick
    assert "50/50 HP" in out
    assert "strike with flame" in out and "Weak to frost" in out


def test_examine_a_plain_foe_notes_no_elemental_nature():
    from parts.world.combat import examine_foe

    s = _fighter()
    npcs.NPCS[_spawn_hostile("brute", atk=5, hp=50)]
    assert "no elemental nature" in examine_foe(s, "brute")


def test_examine_refuses_a_missing_target_a_peaceful_npc_and_an_empty_word():
    from parts.world.combat import examine_foe

    s = _fighter(location="library")
    assert "Examine whom" in examine_foe(s, "")
    assert "no one like that here" in examine_foe(s, "phantom")
    assert "nothing to size up" in examine_foe(s, "librarian")  # peaceful (hp 0)


def test_a_reassembling_foe_quenches_its_burn():
    from parts.world.combat import apply_burn, attack, strike_power

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=strike_power(s))]  # dies to one strike
    apply_burn(npc, damage=4)
    attack(s, "brute")  # the strike fells it -> it reassembles
    assert "burn" not in npc  # the burn is quenched on reassemble


def test_a_reassembling_foe_shakes_off_its_daze():
    from parts.world.combat import apply_daze, attack, strike_power

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=strike_power(s))]  # dies to one strike
    apply_daze(npc, 3)
    attack(s, "brute")  # felled -> reassembles whole
    assert "dazed" not in npc  # the daze is shaken off on reassemble


def test_a_weakened_foe_hits_softer_for_a_set_number_of_blows():
    """A weakened foe's blows land for half (floored 1), one weaken charge spent per blow, until it
    recovers its full strength."""
    from parts.world.combat import _resolve_npc_blow, apply_weaken

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=10, hp=50)]
    full = s.resources["hp"].maximum

    apply_weaken(npc, 2)
    line = _resolve_npc_blow(s, npc, "hits")  # blow 1: softened
    assert full - s.resources["hp"].current == 5  # 10 -> 5
    assert "(weakened)" in line
    assert npc["weakened"] == 1  # one charge spent

    s.resources["hp"] = s.resources["hp"].heal(full)
    _resolve_npc_blow(s, npc, "hits")  # blow 2: softened, last charge
    assert full - s.resources["hp"].current == 5
    assert "weakened" not in npc  # recovered

    s.resources["hp"] = s.resources["hp"].heal(full)
    _resolve_npc_blow(s, npc, "hits")  # blow 3: full strength again
    assert full - s.resources["hp"].current == 10


def test_a_reassembling_foe_recovers_its_full_strength():
    from parts.world.combat import apply_weaken, attack, strike_power

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=strike_power(s))]  # dies to one strike
    apply_weaken(npc, 3)
    attack(s, "brute")  # felled -> reassembles whole
    assert "weakened" not in npc  # the weaken clears on reassemble


# --- endgame: the first boss kill of the day pays a daily bounty --------------------------------


def _spawn_boss(label: str = "warlord", location: str = "courtyard", hp: int = 6, level: int = 3):
    npcs.NPCS[label] = {
        "name": f"the {label}",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": hp,
        "hp_now": hp,
        "xp": 20,
        "atk": 0,
        "level": level,
        "tier": "boss",
    }
    npcs.reindex_npcs()
    return label


def _fell(s: Session, kw: str) -> str:
    out = ""
    for _ in range(20):
        out = attack(s, kw)
        if "collapses" in out:
            return out
    return out


def test_first_boss_kill_of_the_day_pays_a_daily_bounty(monkeypatch):
    from parts.world import lockouts

    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-29")
    s = _fighter()
    _spawn_boss()
    first = _fell(s, "warlord")
    assert "Daily bounty!" in first  # the day's first kill pays extra
    # the boss reassembles and is still farmable, but a second kill the SAME day pays base only
    second = _fell(s, "warlord")
    assert "Daily bounty!" not in second
    assert "You find" in second  # base coins still drop


def test_a_new_day_reopens_the_boss_bounty(monkeypatch):
    from parts.world import lockouts

    s = _fighter()
    _spawn_boss()
    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-29")
    assert "Daily bounty!" in _fell(s, "warlord")
    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-30")
    assert "Daily bounty!" in _fell(s, "warlord")  # the date rolled: the bounty returns


def test_a_normal_foe_pays_no_daily_bounty(monkeypatch):
    from parts.world import lockouts

    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-29")
    s = _fighter()
    out = _fell(s, "dummy")  # the training dummy is no boss
    assert "Daily bounty!" not in out


# --- raids: a boss-tier foe on a WEEKLY lockout, the party's marquee objective -------------------


def _spawn_raid(label: str = "abyssal", location: str = "courtyard", hp: int = 6, level: int = 50):
    npcs.NPCS[label] = {
        "name": f"the {label} guardian",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": hp,
        "hp_now": hp,
        "xp": 40,
        "atk": 0,
        "level": level,
        "tier": "boss",
        "raid": True,
    }
    npcs.reindex_npcs()
    return label


def test_first_raid_kill_of_the_week_pays_a_weekly_bounty(monkeypatch):
    from parts.world import lockouts

    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
    s = _fighter()
    _spawn_raid()
    first = _fell(s, "abyssal")
    assert "Weekly raid bounty!" in first  # the week's first kill pays the marquee reward
    second = _fell(s, "abyssal")
    assert "Weekly raid bounty!" not in second  # farmable, but the bounty is once a week
    assert "You find" in second  # base coins still drop


def test_a_new_week_reopens_the_raid_bounty(monkeypatch):
    from parts.world import lockouts

    s = _fighter()
    _spawn_raid()
    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
    assert "Weekly raid bounty!" in _fell(s, "abyssal")
    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W32")
    assert "Weekly raid bounty!" in _fell(s, "abyssal")  # the week rolled: the raid resets


def test_a_raid_uses_the_weekly_not_the_daily_cadence(monkeypatch):
    # A raid outranks the plain boss branch: it claims the WEEKLY key, not the daily one, so a raid
    # cleared this week does not also silently consume the day's boss lockout.
    from parts.world import lockouts

    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
    s = _fighter()
    _spawn_raid()
    _fell(s, "abyssal")
    assert lockouts.is_locked(s, "raid:abyssal", "2026-W31") is True  # the raid week is claimed
    assert lockouts.is_locked(s, "boss:abyssal", lockouts.today_utc()) is False  # daily untouched


def test_an_empowered_strike_hits_fifty_percent_harder() -> None:
    # the `buff` ability sets the empowered status; combat.attack reads it for a heavier blow
    s = _fighter("vanguard")  # base strike is 7 (3 + strength 14 // 3)
    s.statuses["empowered"] = 3
    out = attack(s, "dummy")
    assert "for 10" in out and "(empowered!)" in out  # 7 + 7//2
