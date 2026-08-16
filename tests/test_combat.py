"""Test twin for kernel/world/combat.py -- deterministic training-loop math."""

import copy
from pathlib import Path

import pytest

from kernel.world import npcs
from kernel.world.combat import attack, strike_power
from kernel.world.jobs import bind_calling
from kernel.world.seed import BlueprintError, Npc, load_npcs
from kernel.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_world():
    # Restore in place (clear + update, never rebind): combat.py holds
    # `from kernel.world.npcs import NPCS`, so rebinding npcs.NPCS would strand that alias.
    from kernel.world import items

    npcs_snap = copy.deepcopy(npcs.NPCS)
    items_snap = copy.deepcopy(items.ITEMS)  # durability tests clone gear; never leak the clones
    SESSIONS.clear()
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    npcs.reindex_npcs()
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
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
    import kernel.world.quest as quest_mod

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
    reassembles: bool = False,
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
    if reassembles:
        hostile["reassembles"] = True
    npcs.NPCS[label] = hostile  # combat.py's NPCS alias sees this (same object, no rebinds)
    npcs.reindex_npcs()
    return label


def test_npc_strike_power_reads_the_atk_stat():
    from kernel.world.combat import npc_strike_power

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
    assert "wake at half health" in out  # the failsafe now leaves a mark
    assert not s.resources["hp"].is_full  # a fall costs something -- no free full restore
    assert s.resources["hp"].current == s.resources["hp"].maximum // 2  # exactly half
    assert s.location == "courtyard"  # restored in place


def test_a_lethal_foe_kills_and_sends_the_player_home():
    from kernel.world.world import START_ROOM

    s = _fighter()  # courtyard, a vanguard
    _spawn_hostile(atk=9999, hp=50, lethal=True)  # a real boss: no training-ground failsafe
    out = attack(s, "brawler")
    assert "wake where your road began" in out and "Training-ground failsafe" not in out
    assert s.location == START_ROOM and s.location != "courtyard"  # sent home, not revived in place
    assert s.resources["hp"].is_full  # full health at the start room
    assert npcs.NPCS["brawler"]["hp_now"] == npcs.NPCS["brawler"]["hp"]  # the boss recovered


def test_an_engineer_emergency_repairs_out_of_a_killing_blow():
    s = _fighter("engineer")
    _spawn_hostile(atk=9999, hp=50)  # a counter that would fell anyone else
    out = attack(s, "brawler")
    assert "Emergency Repair triggers" in out  # the Engineer's reaction fired
    assert s.resources["hp"].current > 0  # pulled back from the fall
    assert "Training-ground failsafe" not in out  # never needed the training-ground failsafe
    assert "emergency_repair" in s.cooldowns  # and armed its cooldown


def test_emergency_repair_fires_once_then_cools_down():
    s = _fighter("engineer")
    _spawn_hostile(atk=9999, hp=9999)  # survives every blow and keeps countering
    first = attack(s, "brawler")
    assert "Emergency Repair triggers" in first  # fires the first time
    second = attack(s, "brawler")
    assert "Emergency Repair" not in second  # on cooldown now
    assert "wake at half health" in second  # so the failsafe catches this fall instead


def test_counterattack_flows_through_the_engine_tick():
    from forge import handle_command

    s = _fighter()
    _spawn_hostile(atk=4, hp=50)
    out = handle_command(s, "attack brawler")
    assert "strikes back for 4" in out


def test_the_seeded_gate_boss_is_a_real_fight():
    """The spiral-ascent Coilwarden is wired for combat: reachable in play, and it hits back."""
    from kernel.world.seed import BLUEPRINTS_ROOT, load_npcs

    boss = load_npcs(BLUEPRINTS_ROOT / "spiral-ascent" / "npcs.yaml")["coilwarden"]
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
    from kernel.world import items

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
    from kernel.world import items

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
        assert "collapses" in out  # the defeat still resolved cleanly
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
    from kernel.world import combat, items

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
    from kernel.world import combat, items

    snap = copy.deepcopy(items.ITEMS)
    try:
        s = _fighter(location="courtyard")
        _felled_foe_with(loot={"copper_key": 1, "nothing": 5})
        monkeypatch.setattr(combat, "_LOOT_RNG", _Rng(6))  # roll 6 -> the last entry (nothing)
        out = attack(s, "goblin")
        assert "drops to the ground" not in out
        assert "collapses" in out  # the defeat still resolved
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(snap)


def test_guaranteed_drops_and_a_weighted_roll_both_fire(monkeypatch):
    from kernel.world import combat, items

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
    with pytest.raises(BlueprintError, match="lethal but has hp 0"):
        load_npcs(p)


def test_the_aethryn_boss_is_lethal():
    seeds = Path(__file__).resolve().parent.parent / "content" / "blueprints"
    aethryn_npcs = load_npcs(seeds / "aethryn" / "npcs.yaml")
    assert aethryn_npcs["netharions_throne_guardian"].get("lethal") is True  # a real boss
    assert aethryn_npcs["veridia_warden"].get("lethal") is not True  # a townsfolk is not lethal


def test_reward_amounts_are_flat_for_a_levelless_foe():
    """A foe without a level keeps the tutorial economy: XP, JP and TP all equal its flat xp."""
    from kernel.world.combat import _reward_amounts

    s = _fighter()
    assert _reward_amounts(s, {"xp": 30}) == (30, 30, 30)


def test_reward_amounts_scale_by_the_challenge_gap_for_a_levelled_foe():
    """Fight up and a levelled foe pays; outclass it by 15+ levels and its xp drops to nothing."""
    from kernel.world.combat import _reward_amounts

    s = _fighter()  # vanguard, player level 1
    s.level = 1
    assert _reward_amounts(s, {"xp": 0, "level": 3, "tier": "normal"})[0] > 0
    s.level = 30  # far past it: a gray
    assert _reward_amounts(s, {"xp": 0, "level": 3, "tier": "normal"})[0] == 0


def test_a_boss_tier_pays_ten_times_a_normal_of_the_same_level():
    from kernel.world.combat import _reward_amounts

    s = _fighter()
    s.level = 5
    normal = _reward_amounts(s, {"xp": 0, "level": 8, "tier": "normal"})
    boss = _reward_amounts(s, {"xp": 0, "level": 8, "tier": "boss"})
    assert boss[0] == normal[0] * 10  # the boss multiplier is x10 the level's base


def test_land_hit_awards_the_scaled_xp_not_the_flat_field():
    """The wiring reaches the grant: a levelled foe with xp:0 still pays its curve reward."""
    from kernel.world.combat import land_hit

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
    from kernel.world.combat import strike_power

    s = _fighter("vanguard")
    s.named = True
    base = strike_power(s)
    s.order = "warcraft"  # ATK +4
    assert strike_power(s) == base + 4


def test_def_from_an_order_mitigates_a_blow_and_a_landed_hit_always_stings():
    """DEF (here from the Making Order) turns a blow, but a hit never drops below 1 damage."""
    from kernel.world.combat import _resolve_npc_blow

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
    from kernel.world.combat import _coin_reward

    assert _coin_reward({"level": 10, "tier": "normal", "xp": 0}) == 10
    assert _coin_reward({"level": 10, "tier": "elite", "xp": 0}) == 30  # elite x3
    assert _coin_reward({"level": 10, "tier": "boss", "xp": 0}) == 100  # boss x10
    assert _coin_reward({"xp": 50}) == 5  # a levelless foe pays a token purse (xp // 10)


def test_a_kill_fills_the_purse():
    from kernel.world.combat import attack

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
    from kernel.world import combat, items

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
    from kernel.world.combat import open_strike

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
    from kernel.world.combat import attack, strike_power

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
    from kernel.world.combat import apply_burn, tick_burns

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
    from kernel.world.combat import apply_burn, tick_burns

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
    from kernel.world.combat import _resolve_npc_blow
    from kernel.world.jobs import JOBS

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
    from kernel.world.combat import _resolve_npc_blow
    from kernel.world.jobs import JOBS

    monkeypatch.setitem(JOBS["vanguard"]["resistances"], "FIR", "Immune")  # would nullify FIR
    s = _fighter("vanguard")
    npc = npcs.NPCS[_spawn_hostile("brute", atk=10, hp=100)]  # untyped: no attack_element
    full = s.resources["hp"].maximum
    _resolve_npc_blow(s, npc, "hits")
    assert full - s.resources["hp"].current == 10  # the full blow: the element gate never fired


def test_an_absorbed_element_heals_instead_of_harming(monkeypatch):
    """Absorb is the deepest resistance: the element mends the player rather than wounding them."""
    from kernel.world.combat import _resolve_npc_blow
    from kernel.world.jobs import JOBS

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
    from kernel.world.combat import typed_hit

    npc = npcs.NPCS[_spawn_hostile("golem", atk=0, hp=500)]
    if grid is not None:
        npc["resistances"] = grid
    dmg, _note = typed_hit(npc, element, 10)
    assert dmg == expected


def test_foe_resistance_defaults_to_normal_without_a_grid():
    from kernel.world.combat import foe_resistance

    npc = npcs.NPCS[_spawn_hostile("golem", atk=0, hp=10)]
    assert foe_resistance(npc, "FIR") == "Normal"  # no grid at all
    npc["resistances"] = {"ICE": "Weak"}
    assert foe_resistance(npc, "FIR") == "Normal"  # a grid that omits the code
    assert foe_resistance(npc, "ICE") == "Weak"


# --- examine: the elemental profile is learnable, not guesswork ---------------------------------


def test_elemental_profile_reads_a_typed_foe():
    from kernel.world.combat import elemental_profile

    npc = npcs.NPCS[_spawn_hostile("wight", atk=5, hp=50)]
    npc["attack_element"] = "FIR"
    npc["resistances"] = {"FIR": "Immune", "ICE": "Weak", "LGT": "Normal"}
    profile = elemental_profile(npc)
    assert "strike with flame" in profile
    assert "Weak to frost" in profile
    assert "Immune to flame" in profile
    assert "lightning" not in profile  # a Normal entry is not a weakness or resistance: omitted


def test_elemental_profile_is_empty_for_a_plain_foe():
    from kernel.world.combat import elemental_profile

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
    from kernel.world.combat import examine_foe

    s = _fighter()
    npcs.NPCS[_spawn_hostile("brute", atk=5, hp=50)]
    assert "no elemental nature" in examine_foe(s, "brute")


def test_examine_refuses_a_missing_target_a_peaceful_npc_and_an_empty_word():
    from kernel.world.combat import examine_foe

    s = _fighter(location="library")
    assert "Examine whom" in examine_foe(s, "")
    assert "no one like that here" in examine_foe(s, "phantom")
    assert "nothing to size up" in examine_foe(s, "librarian")  # peaceful (hp 0)


def test_a_reassembling_foe_quenches_its_burn():
    from kernel.world.combat import apply_burn, attack, strike_power

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=strike_power(s), reassembles=True)]
    apply_burn(npc, damage=4)
    attack(s, "brute")  # the strike fells it -> it reassembles
    assert "burn" not in npc  # the burn is quenched on reassemble


def test_a_reassembling_foe_shakes_off_its_daze():
    from kernel.world.combat import apply_daze, attack, strike_power

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=strike_power(s), reassembles=True)]
    apply_daze(npc, 3)
    attack(s, "brute")  # felled -> reassembles whole
    assert "dazed" not in npc  # the daze is shaken off on reassemble


def test_a_weakened_foe_hits_softer_for_a_set_number_of_blows():
    """A weakened foe's blows land for half (floored 1), one weaken charge spent per blow, until it
    recovers its full strength."""
    from kernel.world.combat import _resolve_npc_blow, apply_weaken

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
    from kernel.world.combat import apply_weaken, attack, strike_power

    s = _fighter()
    npc = npcs.NPCS[_spawn_hostile("brute", atk=0, hp=strike_power(s), reassembles=True)]
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


def _respawn(label: str) -> None:
    """Model a mortal foe's respawn timer elapsing (kernel.world.mortality): it is back at full
    health, present again, ready to fight. Direct unit tests call attack() without running the tick,
    so the world beat never advances to revive it on its own -- this stands in for that passage."""
    npc = npcs.NPCS[label]
    npc.pop("dead_until", None)
    npc["hp_now"] = npc["hp"]


def test_first_boss_kill_of_the_day_pays_a_daily_bounty(monkeypatch):
    from kernel.world import lockouts

    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-29")
    s = _fighter()
    _spawn_boss()
    first = _fell(s, "warlord")
    assert "Daily bounty!" in first  # the day's first kill pays extra
    # the boss dies and respawns on its timer; a second kill the SAME day still pays base only
    _respawn("warlord")
    second = _fell(s, "warlord")
    assert "Daily bounty!" not in second
    assert "You find" in second  # base coins still drop


def test_a_new_day_reopens_the_boss_bounty(monkeypatch):
    from kernel.world import lockouts

    s = _fighter()
    _spawn_boss()
    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-29")
    assert "Daily bounty!" in _fell(s, "warlord")
    _respawn("warlord")  # a day passed: the boss has respawned
    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-30")
    assert "Daily bounty!" in _fell(s, "warlord")  # the date rolled: the bounty returns


def test_a_normal_foe_pays_no_daily_bounty(monkeypatch):
    from kernel.world import lockouts

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
    from kernel.world import lockouts

    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
    s = _fighter()
    _spawn_raid()
    first = _fell(s, "abyssal")
    assert "Weekly raid bounty!" in first  # the week's first kill pays the marquee reward
    _respawn("abyssal")  # the raid boss respawns on its timer
    second = _fell(s, "abyssal")
    assert "Weekly raid bounty!" not in second  # farmable, but the bounty is once a week
    assert "You find" in second  # base coins still drop


def test_a_new_week_reopens_the_raid_bounty(monkeypatch):
    from kernel.world import lockouts

    s = _fighter()
    _spawn_raid()
    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
    assert "Weekly raid bounty!" in _fell(s, "abyssal")
    _respawn("abyssal")  # a week passed: the raid boss has respawned
    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W32")
    assert "Weekly raid bounty!" in _fell(s, "abyssal")  # the week rolled: the raid resets


def test_a_raid_uses_the_weekly_not_the_daily_cadence(monkeypatch):
    # A raid outranks the plain boss branch: it claims the WEEKLY key, not the daily one, so a raid
    # cleared this week does not also silently consume the day's boss lockout.
    from kernel.world import lockouts

    monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
    s = _fighter()
    _spawn_raid()
    _fell(s, "abyssal")
    assert lockouts.is_locked(s, "raid:abyssal", "2026-W31") is True  # the raid week is claimed
    assert lockouts.is_locked(s, "boss:abyssal", lockouts.today_utc()) is False  # daily untouched


def test_a_raid_bounty_scales_with_the_cohort(monkeypatch):
    # A raid rewards a COHORT: the first-kill-of-week bounty pays MORE when a party stood for the
    # kill (solo x1, a duo x2, ...). The co-located band comes from party.members_in_room.
    from kernel.world import lockouts, party

    try:
        solo = _fighter()  # matrym, courtyard
        monkeypatch.setattr(lockouts, "this_week_utc", lambda: "2026-W31")
        _spawn_raid()
        before = solo.coins
        solo_out = _fell(solo, "abyssal")
        solo_gain = solo.coins - before
        assert "Weekly raid bounty!" in solo_out and "cohort" not in solo_out  # solo = x1, no note

        monkeypatch.setattr(
            lockouts, "this_week_utc", lambda: "2026-W32"
        )  # a fresh week for the duo
        SESSIONS["bram"] = Session(player_id="bram", location="courtyard")
        party.invite("matrym", "bram")
        party.join("bram", "matrym")
        assert len(party.members_in_room("matrym", "courtyard")) == 2  # a real cohort
        _spawn_raid()
        before = solo.coins
        duo_out = _fell(solo, "abyssal")
        duo_gain = solo.coins - before
        assert "Weekly raid bounty!" in duo_out and "cohort of 2" in duo_out
        assert duo_gain > solo_gain  # the cohort's bounty scaled higher than the solo lap
    finally:
        party._reset()


def test_a_raid_boss_hits_harder_with_a_cohort():
    # RAID DIFFICULTY scales with the co-located cohort: a solo raider takes the base blow; a band
    # takes +RAID_DIFFICULTY_PER_MEMBER per extra mate, so a raid demands the trinity, not a zerg.
    from kernel.world import party
    from kernel.world.combat import _resolve_npc_blow

    s = _fighter("vanguard")  # matrym, courtyard, no gear -> DEF 0
    s.named = True
    raid_boss = {"name": "a raid boss", "atk": 20, "hp": 9999, "hp_now": 9999, "raid": True}
    try:
        s.resources["hp"] = s.resources["hp"].heal(9999)
        before = s.resources["hp"].current
        _resolve_npc_blow(s, raid_boss, "hits")
        solo = before - s.resources["hp"].current
        assert solo == 20  # solo cohort x1: the base blow (atk 20, DEF 0)

        SESSIONS["bram"] = Session(player_id="bram", location="courtyard")
        SESSIONS["cleo"] = Session(player_id="cleo", location="courtyard")
        party.invite("matrym", "bram")
        party.join("bram", "matrym")
        party.invite("matrym", "cleo")
        party.join("cleo", "matrym")
        assert len(party.members_in_room("matrym", "courtyard")) == 3
        s.resources["hp"] = s.resources["hp"].heal(9999)
        before = s.resources["hp"].current
        _resolve_npc_blow(s, raid_boss, "hits")
        cohort = before - s.resources["hp"].current
        assert cohort == 28 and cohort > solo  # 20 * (1 + 2 * 0.20) = 28
    finally:
        SESSIONS.pop("bram", None)
        SESSIONS.pop("cleo", None)
        party._reset()


def test_a_non_raid_boss_ignores_the_cohort():
    # difficulty-scaling is RAID-only: a plain boss lands the same blow regardless of the cohort.
    from kernel.world import party
    from kernel.world.combat import _resolve_npc_blow

    s = _fighter("vanguard")
    s.named = True
    plain_boss = {"name": "a brute", "atk": 20, "hp": 9999, "hp_now": 9999, "tier": "boss"}
    try:
        SESSIONS["bram"] = Session(player_id="bram", location="courtyard")
        party.invite("matrym", "bram")
        party.join("bram", "matrym")
        s.resources["hp"] = s.resources["hp"].heal(9999)
        before = s.resources["hp"].current
        _resolve_npc_blow(s, plain_boss, "hits")
        assert before - s.resources["hp"].current == 20  # no raid flag: cohort is ignored
    finally:
        SESSIONS.pop("bram", None)
        party._reset()


def test_an_empowered_strike_hits_fifty_percent_harder() -> None:
    # the `buff` ability sets the empowered status; combat.attack reads it for a heavier blow
    s = _fighter("vanguard")  # base strike is 7 (3 + strength 14 // 3)
    s.statuses["empowered"] = 3
    out = attack(s, "dummy")
    assert "for 10" in out and "(empowered!)" in out  # 7 + 7//2


# --- durability: gear wears in combat (the economy's sink) ---------------------------------------


def test_a_landed_strike_wears_the_equipped_weapon():
    from kernel.world import durability, items

    s = _fighter()
    s.equipped["weapon"] = items.clone("forge_wrench", items.carrier("matrym"))
    attack(s, "dummy")
    assert durability.current(s.equipped["weapon"]) == durability.MAX - 1  # the strike dulled it


# --- K2: a lethal death batters worn gear; the training-ground failsafe stays gentle -------------


def test_a_lethal_death_batters_worn_gear():
    from kernel.world import durability, items
    from kernel.world.combat import DEATH_DURABILITY_TOLL

    s = _fighter()
    s.equipped["weapon"] = items.clone("forge_wrench", items.carrier("matrym"))
    _spawn_hostile(atk=9999, hp=50, lethal=True)  # a real boss: its blow fells the hero
    out = attack(s, "brawler")
    assert "battered in the fall" in out  # the fall message names the gear stake
    # the strike itself dulled the weapon 1 point before the counter fell the hero; the death toll
    # adds DEATH_DURABILITY_TOLL more on top of that.
    assert durability.current(s.equipped["weapon"]) == durability.MAX - 1 - DEATH_DURABILITY_TOLL


def test_the_training_ground_failsafe_does_not_batter_gear():
    from kernel.world import durability, items

    s = _fighter()  # a vanguard: no Engineer reaction, so a huge counter triggers the failsafe
    s.equipped["weapon"] = items.clone("forge_wrench", items.carrier("matrym"))
    _spawn_hostile(atk=9999, hp=50)  # NON-lethal: the training-ground failsafe catches the fall
    out = attack(s, "brawler")
    assert "wake at half health" in out  # the gentle failsafe fired
    # only the normal strike-wear (1 point) landed; the failsafe added NO death gear toll (else -11)
    assert durability.current(s.equipped["weapon"]) == durability.MAX - 1


def test_a_bare_hero_takes_no_gear_toll_on_a_lethal_death():
    s = _fighter()  # nothing equipped
    _spawn_hostile(atk=9999, hp=50, lethal=True)
    out = attack(s, "brawler")
    assert "battered in the fall" not in out  # no gear, no gear message


def test_a_lethal_death_sets_xp_progress_back_without_de_leveling():
    from kernel.world.progression_awards import award_xp

    s = _fighter()
    award_xp(s, 100)  # level 2 (needs 75), 25 XP into the level
    assert s.level == 2
    _spawn_hostile(atk=9999, hp=50, lethal=True)
    out = attack(s, "brawler")
    assert "sets your progress back" in out  # the fall names the XP stake
    assert s.level == 2  # the LEVEL holds
    assert 75 <= s.xp < 100  # lost progress, never below the level's floor


def test_the_training_ground_failsafe_costs_no_xp():
    from kernel.world.progression_awards import award_xp

    s = _fighter()
    award_xp(s, 100)
    _spawn_hostile(atk=9999, hp=50)  # NON-lethal: the failsafe, not a real death
    attack(s, "brawler")
    assert s.xp == 100  # the gentle failsafe never costs progress


def test_a_recleared_boss_is_acknowledged_not_silently_farmed(monkeypatch):
    from kernel.world import lockouts

    monkeypatch.setattr(lockouts, "today_utc", lambda: "2026-07-29")
    s = _fighter()
    _spawn_boss()
    assert "Daily bounty!" in _fell(s, "warlord")  # first clear pays the bounty
    _respawn("warlord")
    second = _fell(s, "warlord")
    assert "already cleared today" in second  # the clear is surfaced, not silent
    assert "Daily bounty!" not in second  # but the bounty does not repeat


def test_a_landed_blow_wears_the_equipped_body_armor():
    from kernel.world import durability, items
    from kernel.world.aggression import menace

    s = _fighter()
    s.equipped["body"] = items.clone("padded_jerkin", items.carrier("matrym"))
    npcs.NPCS["reaver"] = {
        "name": "the reaver",
        "keywords": ["reaver"],
        "location": "courtyard",
        "dialogue": ["..."],
        "next_line": 0,
        "hp": 60,
        "hp_now": 60,
        "xp": 10,
        "atk": 5,
        "aggressive": True,
    }
    npcs.reindex_npcs()
    menace(s)  # the reaver strikes the fighter on the beat
    assert durability.current(s.equipped["body"]) == durability.MAX - 1  # the blow dented it


# --- Combat variance (the one die on a blow) and death stakes ---------------------------------


class _ForceRng:
    """Forces combat's variance die to a chosen roll, so a test can pin an exact outcome. The suite
    installs a neutral RNG (conftest); a variance test installs this to demand miss/crit/glance."""

    def __init__(self, roll: float) -> None:
        self._roll = roll

    def random(self) -> float:
        return self._roll


def test_apply_variance_covers_every_band(monkeypatch):
    """The variance die maps its roll to (damage, note): a miss zeroes the blow, a crit doubles it,
    a glance halves it (floored 1), a normal hit passes through, a zero blow never rolls."""
    from kernel.world import combat

    def force(roll: float) -> None:
        monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(roll))

    force(0.0)
    assert combat._apply_variance(10) == (0, " (miss!)")
    force(0.10)
    assert combat._apply_variance(10) == (20, " (critical!)")  # CRIT_MULT x 10
    force(0.20)
    assert combat._apply_variance(10) == (5, " (glancing)")  # 10 // 2
    force(0.99)
    assert combat._apply_variance(10) == (10, "")  # normal: unchanged
    force(0.0)
    assert combat._apply_variance(0) == (0, "")  # nothing to roll on a zero blow


def test_a_critical_strike_doubles_the_players_blow(monkeypatch):
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(0.10))  # crit band
    s = _fighter()  # strike_power 7
    out = attack(s, "dummy")
    assert "for 14" in out and "(critical!)" in out  # 7 doubled, and tagged


def test_a_missed_strike_deals_nothing_and_reads_as_a_whiff(monkeypatch):
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(0.0))  # miss band
    s = _fighter()
    out = attack(s, "dummy")
    assert "and miss" in out  # the whiff line, not a strike line
    assert npcs.NPCS["training_dummy"]["hp_now"] == 20  # the dummy took nothing


def test_a_glancing_strike_lands_soft(monkeypatch):
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(0.20))  # glance band
    s = _fighter()  # strike_power 7
    out = attack(s, "dummy")
    assert "for 3" in out and "(glancing)" in out  # 7 // 2, tagged


def test_an_npc_blow_can_crit(monkeypatch):
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(0.10))  # crit band
    s = _fighter()
    _spawn_hostile(atk=5, hp=50)
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")  # the counter rides the same die
    assert "strikes back for 10" in out and "(critical!)" in out  # atk 5 doubled
    assert s.resources["hp"].current == max_hp - 10


def test_an_npc_blow_can_miss(monkeypatch):
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(0.0))  # miss band
    s = _fighter()
    _spawn_hostile(atk=5, hp=50)
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")
    assert "strikes back" in out and "(miss!)" in out  # the counter whiffed
    assert s.resources["hp"].current == max_hp  # unhurt


def test_a_telegraphed_unleash_never_whiffs(monkeypatch):
    """A guaranteed special was telegraphed and connects by design: the miss die does not apply."""
    from kernel.world import combat

    monkeypatch.setattr(combat, "_COMBAT_RNG", _ForceRng(0.0))  # would MISS a normal blow
    s = _fighter()
    _spawn_hostile(atk=10, hp=50)
    npc = npcs.NPCS["brawler"]
    npc["special"] = {"telegraph": "it winds up", "mult": 2}
    npc["charging"] = True  # mid-unleash: this beat lands
    max_hp = s.resources["hp"].maximum
    out = attack(s, "brawler")
    assert "unleashes its special" in out
    assert "(miss!)" not in out  # the guaranteed blow ignored the miss die
    assert s.resources["hp"].current < max_hp  # it connected


def test_a_fall_scatters_carried_coins_and_wakes_at_half():
    s = _fighter()
    s.coins = 100
    _spawn_hostile(atk=9999, hp=50)  # its counter empties the player's HP
    out = attack(s, "brawler")
    assert s.coins == 90  # a tenth of the carried purse scattered
    assert "scatter" in out
    assert s.resources["hp"].current == s.resources["hp"].maximum // 2  # woke at half, not full


def test_a_penniless_fall_scatters_nothing():
    s = _fighter()  # an empty purse
    _spawn_hostile(atk=9999, hp=50)
    out = attack(s, "brawler")
    assert "scatter" not in out  # nothing to lose, no toll line
    assert s.coins == 0


def test_a_lethal_fall_also_scatters_coins():
    from kernel.world.world import START_ROOM

    s = _fighter()
    s.coins = 100
    _spawn_hostile(atk=9999, hp=50, lethal=True)  # a real boss
    out = attack(s, "brawler")
    assert s.coins == 90  # the toll applies to a lethal fall too
    assert "scatters from your purse" in out
    assert s.location == START_ROOM
    assert s.resources[
        "hp"
    ].is_full  # full health at the start room (the trip home is its own stake)


# --- numbered-target disambiguation: attack the Nth of several identical foes ---------------------
def _spawn_two_goblins(location: str = "courtyard") -> None:
    """Two identical foes sharing the keyword 'goblin', so a bare 'goblin' is ambiguous."""
    for i in (1, 2):
        npcs.NPCS[f"goblin_{i}"] = {
            "name": f"goblin {i}",
            "keywords": ["goblin"],
            "location": location,
            "dialogue": ["..."],
            "next_line": 0,
            "hp": 50,
            "hp_now": 50,
            "xp": 10,
            "atk": 0,
        }
    npcs.reindex_npcs()


def test_bare_attack_hits_the_first_of_two_identical_foes():
    s = _fighter()
    _spawn_two_goblins()
    out = attack(s, "goblin")
    assert "goblin 1" in out
    assert npcs.NPCS["goblin_1"]["hp_now"] < 50  # the first took the blow
    assert npcs.NPCS["goblin_2"]["hp_now"] == 50  # the second is untouched


def test_attack_ordinal_strikes_the_second_identical_foe():
    """The defect this fixes: first-match-only targeting left a second identical foe unhittable."""
    s = _fighter()
    _spawn_two_goblins()
    out = attack(s, "2-goblin")
    assert "goblin 2" in out
    assert npcs.NPCS["goblin_2"]["hp_now"] < 50  # the SECOND took the blow
    assert npcs.NPCS["goblin_1"]["hp_now"] == 50  # the first is untouched


def test_attack_overshoot_is_refused_with_a_count():
    s = _fighter()
    _spawn_two_goblins()
    out = attack(s, "3-goblin")
    assert "There is no one like that here" in out
    assert "only 2 here" in out
    # nobody was struck
    assert npcs.NPCS["goblin_1"]["hp_now"] == 50
    assert npcs.NPCS["goblin_2"]["hp_now"] == 50
