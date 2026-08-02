"""Test twin for kernel/world/abilities.py + seed.load_abilities -- usable combat moves.

Acceptance: a job wields its abilities (a strike scales on a stat and reuses the combat defeat path;
a heal restores HP), each spends MP, and `use`/`skills` are reachable through the engine tick.
Refusal: no calling, an unknown ability, an ability another job owns, too little MP, and a missing
or dead target all fail loud. Load: a malformed ability (bad kind/scales, negative power) fails at
seed load.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

import forge
from kernel.world import npcs
from kernel.world.abilities import abilities_for, render_abilities, use_ability
from kernel.world.seed import Npc, SeedError, load_abilities
from kernel.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_npcs():
    """Snapshot the NPC table (combat mutates the dummy's hp) and restore it after each test."""
    snap = copy.deepcopy(npcs.NPCS)
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(snap)
    SESSIONS.clear()  # ally-heal tests seat sessions; never leak them to the next test


def _at_dummy(job: str) -> Session:
    """A session with `job`, standing in the courtyard where the training dummy waits."""
    s = Session(player_id="hero")
    forge.handle_command(s, f"job {job}")
    forge.handle_command(s, "go north")  # forge -> courtyard (the dummy's room)
    return s


# --- the ability data maps jobs correctly (first-forge seed) -------------------------------------


def test_abilities_map_to_the_jobs_that_declare_them() -> None:
    assert [a["name"] for _, a in abilities_for("scholar")] == [
        "Arcane Bolt",
        "Cleansing Light",
        "Corrode",
        "Mend",
    ]
    assert [a["name"] for _, a in abilities_for("vanguard")] == [
        "Bulwark Challenge",
        "Power Strike",
        "Rally",
    ]
    assert abilities_for("") == []  # no calling, no abilities


# --- strike: scales on a stat, spends MP, reuses the combat defeat path --------------------------


def test_a_strike_ability_hits_harder_than_a_basic_attack_and_costs_mp() -> None:
    s = _at_dummy("engineer")
    mp_before = s.resources["mp"].current
    out = use_ability(s, "power strike on dummy")
    assert "Power Strike" in out and "training dummy" in out
    assert s.resources["mp"].current == mp_before - 3  # Power Strike costs 3 MP
    # Power Strike (6 + strength/3) lands more than the basic attack (3 + strength/3)
    dealt = int(out.split(" for ")[1].split(".")[0])
    assert dealt > 6


# --- drain: lifesteal -- strike the foe and recover half the damage as HP ------------------------


def test_a_drain_ability_deals_damage_and_heals_the_wielder() -> None:
    s = _at_dummy("artificer")
    s.resources["hp"] = s.resources["hp"].damage(20)  # take a wound the siphon can restore
    hp_before = s.resources["hp"].current
    mp_before = s.resources["mp"].current
    out = use_ability(s, "siphon on dummy")
    assert "Siphon" in out and "training dummy" in out and "recover" in out
    assert s.resources["mp"].current == mp_before - 4  # Siphon costs 4 MP
    assert s.resources["hp"].current > hp_before  # lifesteal siphoned HP back to the wielder


def test_a_drain_never_overheals_past_the_maximum() -> None:
    s = _at_dummy("artificer")
    full = s.resources["hp"].current  # already at full HP
    use_ability(s, "siphon on dummy")
    assert s.resources["hp"].current == full  # a siphon at full HP wastes no overheal


# --- regen: a woven heal-over-time that mends across the world beats -----------------------------
def test_a_regen_ability_mends_over_the_world_beat() -> None:
    from kernel.world.afflictions import tick_regens

    s = _at_dummy("artificer")
    s.resources["hp"] = s.resources["hp"].damage(30)  # take a wound the HoT can mend
    out = use_ability(s, "repair field")  # a regen on self
    assert "Repair Field" in out and "mend" in out
    assert s.regens  # a heal-over-time boon is now active
    hp_before = s.resources["hp"].current
    tick_regens(s)  # one world beat
    assert s.resources["hp"].current > hp_before  # the boon mended HP on the beat


# --- kit density: EVERY aethryn calling carries a full, coherent moveset (batches 1-3) -----------
def test_every_aethryn_calling_has_a_full_kit() -> None:
    from collections import Counter, defaultdict

    ab = load_abilities(Path("seeds/aethryn/abilities.yaml"))
    per: Counter = Counter()
    kinds: dict[str, set] = defaultdict(set)
    for a in ab.values():
        for job in a["jobs"]:
            per[job] += 1
            kinds[job].add(a["kind"])
    # After the three density passes, every playable calling has a full 5-ability kit with >=2 kinds
    # (a role identity, not just a pile of strikes). `template` is the non-playable base row.
    thin = sorted(f"{j}({c})" for j, c in per.items() if j != "template" and c < 5)
    assert not thin, f"callings without a full 5-ability kit: {thin}"
    one_note = sorted(j for j, ks in kinds.items() if j != "template" and len(ks) < 2)
    assert not one_note, f"callings with a one-note kit: {one_note}"


@pytest.mark.parametrize("job", ["vanguard", "scholar", "artificer", "engineer"])
def test_every_approved_calling_is_playable_end_to_end(job: str) -> None:
    """Guards Stage 3's "all approved Callings are implemented": each calling can be
    taken, lists its abilities, and fires one of its OWN strike moves at the dummy
    through the engine tick -- not merely present in the data."""
    strikes = [a for _, a in abilities_for(job) if a["kind"] == "strike"]
    assert strikes, f"{job} has no strike ability to prove combat play"
    name = strikes[0]["name"]
    s = _at_dummy(job)
    assert name in forge.handle_command(s, "skills")
    out = forge.handle_command(s, f"use {name.lower()} on dummy")
    assert name in out and "training dummy" in out and " for " in out


def test_a_heal_ability_restores_hp_and_costs_mp() -> None:
    s = _at_dummy("scholar")
    s.resources["hp"] = s.resources["hp"].damage(10)
    hp_before, mp_before = s.resources["hp"].current, s.resources["mp"].current
    out = use_ability(s, "mend")
    assert "Mend" in out and "recover" in out
    assert s.resources["hp"].current > hp_before
    assert s.resources["mp"].current == mp_before - 5


def _seated(job: str, pid: str, location: str = "courtyard") -> Session:
    """A session with a calling, seated in SESSIONS at a room (so _trace_ally can find it)."""
    s = Session(player_id=pid)
    forge.handle_command(s, f"job {job}")
    s.location = location
    SESSIONS[pid] = s
    return s


# --- the trinity seam: a heal can mend an ally in the room --------------------------------------


def test_a_heal_mends_a_wounded_ally_in_the_room() -> None:
    healer = _seated("scholar", "cleo")
    ally = _seated("vanguard", "bram")
    ally.resources["hp"] = ally.resources["hp"].damage(12)
    ally_before, healer_hp_before = ally.resources["hp"].current, healer.resources["hp"].current
    mp_before = healer.resources["mp"].current
    out = use_ability(healer, "mend on bram")
    assert "on Bram" in out and "mending" in out
    assert ally.resources["hp"].current > ally_before  # the ally was healed
    assert healer.resources["hp"].current == healer_hp_before  # not the healer
    assert healer.resources["mp"].current == mp_before - 5  # the healer paid


def test_a_heal_on_self_by_name_still_heals_the_wielder() -> None:
    healer = _seated("scholar", "cleo")
    healer.resources["hp"] = healer.resources["hp"].damage(10)
    before = healer.resources["hp"].current
    out = use_ability(healer, "mend on me")
    assert "recover" in out
    assert healer.resources["hp"].current > before


def test_healing_an_absent_ally_fails_loud_and_keeps_the_mp() -> None:
    healer = _seated("scholar", "cleo")
    mp_before = healer.resources["mp"].current
    out = use_ability(healer, "mend on nobody")
    assert "no ally called 'nobody'" in out
    assert healer.resources["mp"].current == mp_before  # MP never burned into the void


def test_a_heal_will_not_reach_an_ally_in_another_room() -> None:
    healer = _seated("scholar", "cleo", location="courtyard")
    _seated("vanguard", "bram", location="forge")  # same world, different room
    out = use_ability(healer, "mend on bram")
    assert "no ally called 'bram'" in out  # room-local: out of reach elsewhere


def test_healing_a_name_no_one_in_the_room_answers_to_fails_loud() -> None:
    healer = _seated("scholar", "cleo")
    _seated("vanguard", "bram")  # a real ally present, but not the one named
    out = use_ability(healer, "mend on ghost")  # scans the room, finds no match
    assert "no ally called 'ghost'" in out


def test_render_abilities_shows_a_heal_targets_self_or_ally() -> None:
    healer = _seated("scholar", "cleo")
    out = render_abilities(healer)
    assert "self or ally" in out


def test_a_strike_that_fells_the_dummy_still_awards_and_reassembles() -> None:
    s = _at_dummy("engineer")
    npcs.NPCS["training_dummy"]["hp_now"] = 1  # one hit from defeat
    out = use_ability(s, "power strike on dummy")
    assert "collapses" in out and "reassembles" in out  # reused the defeat machinery
    assert npcs.NPCS["training_dummy"]["hp_now"] == npcs.NPCS["training_dummy"]["hp"]  # reassembled


# --- refusals ------------------------------------------------------------------------------------


def test_no_calling_refuses() -> None:
    assert "no calling" in use_ability(Session(player_id="x"), "power strike on dummy")


def test_an_unknown_ability_refuses() -> None:
    assert "no ability called 'nonsense'" in use_ability(_at_dummy("engineer"), "nonsense on dummy")


def test_an_ability_another_job_owns_refuses() -> None:
    # the engineer cannot wield Mend (a scholar ability) -- named, not silently ignored
    assert "cannot wield Mend" in use_ability(_at_dummy("engineer"), "mend")


def test_too_little_mp_refuses_and_spends_nothing() -> None:
    s = _at_dummy("engineer")
    s.resources["mp"] = s.resources["mp"].damage(s.resources["mp"].current)  # drain MP to 0
    out = use_ability(s, "power strike on dummy")
    assert "Not enough MP" in out and s.resources["mp"].current == 0


def test_a_missing_target_refuses() -> None:
    assert "on whom?" in use_ability(_at_dummy("engineer"), "power strike")


# --- reachable through the engine tick -----------------------------------------------------------


def test_use_and_skills_are_wired_to_the_tick() -> None:
    s = _at_dummy("engineer")
    assert "Power Strike" in forge.handle_command(s, "skills")
    assert "training dummy" in forge.handle_command(s, "use power strike on dummy")


def test_skills_without_a_calling_refuses() -> None:
    assert "no calling" in render_abilities(Session(player_id="x"))


# --- load-time validation (fail loud on a bad ability) -------------------------------------------


def _abilities_file(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "abilities.yaml"
    p.write_text(body)
    return p


def test_every_shipped_seed_abilities_file_loads() -> None:
    # every seeds/<world>/abilities.yaml is valid data (fails loud here, not at a player's boot)
    seeds = Path(__file__).resolve().parent.parent / "content" / "seeds"
    files = sorted(seeds.glob("*/abilities.yaml"))
    assert files  # at least first-forge ships one
    for f in files:
        assert load_abilities(f)  # non-empty and well-formed


def test_aethryn_ships_a_moveset_for_each_calling() -> None:
    from kernel.world.seed import load_jobs

    seeds = Path(__file__).resolve().parent.parent / "content" / "seeds"
    ab = load_abilities(seeds / "aethryn" / "abilities.yaml")
    wielders = {job for a in ab.values() for job in a["jobs"]}
    callings = set(load_jobs(seeds / "aethryn" / "jobs.yaml"))  # loader drops 'template'
    assert wielders == callings  # EVERY aethryn calling is armed (no unarmed switchable job)


def test_load_abilities_accepts_a_wellformed_file(tmp_path: Path) -> None:
    p = _abilities_file(
        tmp_path,
        "jab:\n  name: Jab\n  kind: strike\n  power: 4\n"
        "  scales: strength\n  mp_cost: 2\n  cooldown: 2\n  jobs: [vanguard]\n",
    )
    loaded = load_abilities(p)
    assert loaded["jab"]["name"] == "Jab" and loaded["jab"]["scales"] == "strength"
    assert loaded["jab"]["cooldown"] == 2  # the cadence knob loads
    # a bare ability (no cooldown declared) stays uncapped -- the key is simply absent
    bare = load_abilities(_abilities_file(tmp_path, "poke:\n  kind: strike\n  jobs: [vanguard]\n"))
    assert "cooldown" not in bare["poke"]


def test_skills_for_a_calling_with_no_abilities() -> None:
    s = Session(player_id="wanderer")
    forge.handle_command(s, "job vanguard")  # stats set
    s.job = "unlisted"  # a calling no ability declares
    assert "no abilities yet" in render_abilities(s)


def test_using_an_ability_on_a_peaceful_npc_refuses() -> None:
    s = Session(player_id="hero")
    forge.handle_command(s, "job engineer")
    forge.handle_command(s, "go north")  # forge -> courtyard
    forge.handle_command(s, "go east")  # courtyard -> library (the peaceful librarian, hp 0)
    assert "not something you can fight" in use_ability(s, "power strike on librarian")


@pytest.mark.parametrize(
    "body, match",
    [
        ("bad:\n  kind: explode\n  jobs: [vanguard]\n", "'strike', 'heal', 'brand', 'daze'"),
        (
            "bad:\n  kind: strike\n  scales: charisma\n  jobs: [vanguard]\n",
            "'scales' must be an attribute",
        ),
        (
            "bad:\n  kind: strike\n  power: -3\n  jobs: [vanguard]\n",
            "'power' must be a non-negative",
        ),
        (
            "bad:\n  kind: strike\n  power: 4\n  cooldown: -1\n  jobs: [vanguard]\n",
            "'cooldown' must be a non-negative",
        ),
    ],
)
def test_load_abilities_refuses_a_malformed_ability(tmp_path: Path, body: str, match: str) -> None:
    with pytest.raises(SeedError, match=match):
        load_abilities(_abilities_file(tmp_path, body))


# --- subjob lends its kit: switching a subjob opens a different moveset (FFXI-style) -------------


def test_a_subjob_lends_its_kit_so_switching_opens_a_new_moveset() -> None:
    from kernel.world.abilities import abilities_for_session
    from kernel.world.jobs import set_secondary

    s = _at_dummy("vanguard")
    # primary only: the vanguard's own kit (a strike + the taunt), before any subjob is lent
    assert [a["name"] for _, a in abilities_for_session(s)] == [
        "Bulwark Challenge",
        "Power Strike",
        "Rally",
    ]
    set_secondary(s, "scholar")
    names = {a["name"] for _, a in abilities_for_session(s)}
    assert {"Power Strike", "Arcane Bolt", "Mend"} <= names  # the subjob's moves are lent


def test_a_subjob_ability_is_wieldable_not_refused_by_calling() -> None:
    from kernel.world.jobs import set_secondary

    s = _at_dummy("vanguard")
    assert "cannot wield" in use_ability(s, "arcane bolt on dummy")  # refused before a subjob
    set_secondary(s, "scholar")
    after = use_ability(s, "arcane bolt on dummy")
    assert "cannot wield" not in after  # the subjob lends it (may still gate on MP, not on calling)


def test_render_abilities_marks_the_subjob_moves() -> None:
    from kernel.world.jobs import set_secondary

    s = _at_dummy("vanguard")
    set_secondary(s, "scholar")
    out = render_abilities(s)
    assert "Arcane Bolt" in out and "(subjob)" in out  # the borrowed moves are flagged


def test_a_daze_ability_dazes_a_foe_without_damage() -> None:
    """A `daze` is pure crowd control: it sets the foe's daze counter (power = beats) and deals no
    damage. Covers the daze branch of use_ability."""
    s = _at_dummy("engineer")  # the engineer wields Concuss (daze, power 2)
    dummy = npcs.NPCS["training_dummy"]
    hp_before = dummy["hp_now"]
    out = use_ability(s, "concuss on dummy")
    assert "daze" in out.lower() and dummy.get("dazed") == 2  # power 2 -> 2 beats
    assert dummy["hp_now"] == hp_before  # a daze does no immediate damage


def test_a_weaken_ability_softens_a_foe_without_damage() -> None:
    """A `weaken` sets the foe's weaken counter (power = blows) and deals no damage. Covers the
    weaken branch of use_ability."""
    s = _at_dummy("artificer")  # the artificer wields Sunder Guard (weaken, power 3)
    dummy = npcs.NPCS["training_dummy"]
    hp_before = dummy["hp_now"]
    out = use_ability(s, "sunder guard on dummy")
    assert "weaken" in out.lower() and dummy.get("weakened") == 3  # power 3 -> 3 blows
    assert dummy["hp_now"] == hp_before  # a weaken does no immediate damage


def test_a_brand_ability_burns_the_target_on_the_world_beat() -> None:
    """A `brand` lays a burn (no immediate damage); the burn saps HP on each world beat, so a
    following command shows the foe smoulder. Covers the brand path AND the beat wiring."""
    s = _at_dummy("scholar")
    dummy = npcs.NPCS["training_dummy"]
    out = use_ability(s, "corrode on dummy")
    assert "brand" in out.lower() and dummy.get("burn") is not None
    assert dummy["hp_now"] == dummy["hp"]  # a brand does no immediate damage
    beat = forge.handle_command(s, "look")  # the world beat ticks the burn
    assert "smoulders" in beat
    assert dummy["hp_now"] < dummy["hp"]  # the burn sapped HP


# --- elemental abilities: the foe's resistance scales the player's typed hit --------------------


def _durable_foe(resistances: dict[str, str] | None = None) -> Npc:
    """A high-HP courtyard foe that survives a strike, so a damage delta is measurable."""
    foe: Npc = {
        "name": "the golem",
        "keywords": ["golem"],
        "location": "courtyard",
        "dialogue": ["..."],
        "next_line": 0,
        "hp": 500,
        "hp_now": 500,
        "xp": 10,
        "atk": 0,
    }
    if resistances is not None:
        foe["resistances"] = resistances
    npcs.NPCS["golem"] = foe
    return foe


def test_a_typed_strike_tears_into_a_weak_foe(monkeypatch) -> None:
    """An ability's element meets the foe's resistance grid: a Weak foe takes +50% (freeze the fire
    creature, don't burn it). This is the mirror of a foe's typed blow vs the player's grid."""
    from kernel.world.abilities import ABILITIES

    s = _at_dummy("engineer")
    foe = _durable_foe()
    use_ability(s, "power strike on golem")  # untyped baseline
    base = 500 - foe["hp_now"]
    foe["hp_now"] = 500
    monkeypatch.setitem(ABILITIES["power_strike"], "element", "FIR")
    monkeypatch.setitem(foe, "resistances", {"FIR": "Weak"})
    out = use_ability(s, "power strike on golem")
    assert 500 - foe["hp_now"] == base + base // 2  # +50% into the weakness
    assert "tears into it" in out


def test_a_typed_strike_is_nullified_by_an_immune_foe(monkeypatch) -> None:
    from kernel.world.abilities import ABILITIES

    s = _at_dummy("engineer")
    foe = _durable_foe({"FIR": "Immune"})
    monkeypatch.setitem(ABILITIES["power_strike"], "element", "FIR")
    out = use_ability(s, "power strike on golem")
    assert foe["hp_now"] == 500  # no damage landed
    assert "immune to flame" in out


def test_an_untyped_strike_ignores_a_foes_resistance() -> None:
    """A move with no element deals physical damage a resistance never touches (backward-compat:
    every existing untyped ability fights exactly as before)."""
    s = _at_dummy("engineer")
    foe = _durable_foe({"FIR": "Immune"})  # would nullify a FIR strike, but the move is untyped
    out = use_ability(s, "power strike on golem")
    assert 500 - foe["hp_now"] > 0  # the full blow landed: the element gate never fired
    assert "immune" not in out


def test_a_typed_brand_is_refused_by_an_immune_foe(monkeypatch) -> None:
    from kernel.world.abilities import ABILITIES

    s = _at_dummy("scholar")  # the scholar wields Corrode (a brand)
    foe = _durable_foe({"FIR": "Immune"})
    monkeypatch.setitem(ABILITIES["corrode"], "element", "FIR")
    out = use_ability(s, "corrode on golem")
    assert "immune to flame" in out
    assert "burn" not in foe  # no burn took hold on an immune foe


def test_load_abilities_rejects_an_unknown_element(tmp_path: Path) -> None:
    body = "bad:\n  kind: strike\n  element: PLASMA\n  jobs: [vanguard]\n"
    with pytest.raises(SeedError, match="element"):
        load_abilities(_abilities_file(tmp_path, body))


def test_load_abilities_accepts_a_typed_ability(tmp_path: Path) -> None:
    body = "zap:\n  name: Zap\n  kind: strike\n  element: LGT\n  jobs: [vanguard]\n"
    assert load_abilities(_abilities_file(tmp_path, body))["zap"]["element"] == "LGT"


# --- ability cooldowns: cadence turns spam into a rotation ---------------------------------------


def test_a_cooldown_locks_the_ability_until_a_landed_strike_thaws_it(monkeypatch) -> None:
    """The cadence gate: a cooldown'd ability locks after use, is refused while recovering, and
    thaws as the combat clock advances (a landed strike -- basic attack -- ages every cooldown)."""
    from kernel.world.abilities import ABILITIES
    from kernel.world.combat import attack

    s = _at_dummy("engineer")  # the engineer wields Power Strike (a strike)
    monkeypatch.setitem(ABILITIES["power_strike"], "cooldown", 2)

    first = use_ability(s, "power strike on dummy")
    assert "Power Strike" in first
    assert s.cooldowns.get("power_strike") == 2  # armed to full AFTER its own clock advance

    locked = use_ability(s, "power strike on dummy")
    assert "still recovering" in locked  # refused while on cooldown
    assert s.resources["mp"].current  # (sanity: a refusal spends nothing it shouldn't)

    attack(s, "dummy")  # a landed strike advances the clock: cooldown 2 -> 1
    assert s.cooldowns.get("power_strike") == 1
    attack(s, "dummy")  # 1 -> 0, and the expired cooldown drops off
    assert "power_strike" not in s.cooldowns
    assert "Power Strike" in use_ability(s, "power strike on dummy")  # ready again


def test_a_no_cooldown_ability_never_locks() -> None:
    # first-forge's abilities ship no cooldowns (a gentle tutorial), so using one arms nothing.
    s = _at_dummy("scholar")
    use_ability(s, "arcane bolt on dummy")
    assert "arcane_bolt" not in s.cooldowns


def test_skills_shows_a_cooldown_and_its_live_recovery(monkeypatch) -> None:
    from kernel.world.abilities import ABILITIES

    s = _at_dummy("engineer")
    monkeypatch.setitem(ABILITIES["power_strike"], "cooldown", 3)
    assert "3b cooldown" in render_abilities(s)  # advertised cadence
    use_ability(s, "power strike on dummy")
    assert "recovering 3b" in render_abilities(s)  # live recovery state


def test_the_aethryn_seed_arms_a_rotation() -> None:
    # aethryn (the flagship) gives powerful moves real cooldowns while light strikes stay filler.
    ab = load_abilities(
        Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn" / "abilities.yaml"
    )
    assert any(a.get("cooldown", 0) > 0 for a in ab.values())  # a rotation exists
    assert any(a.get("cooldown", 0) == 0 for a in ab.values())  # spammable filler remains


# --- taunt: the tank forces a foe's aggro onto itself -------------------------------------------


def _aggressor(label: str = "reaver", location: str = "courtyard", atk: int = 5) -> str:
    """Place an aggressive foe in a room (so heal/taunt threat has a target)."""
    npcs.NPCS[label] = {
        "name": f"the {label}",
        "keywords": [label],
        "location": location,
        "dialogue": ["..."],
        "next_line": 0,
        "hp": 80,
        "hp_now": 80,
        "xp": 10,
        "atk": atk,
        "aggressive": True,
    }
    npcs.reindex_npcs()
    return label


def test_a_taunt_forces_the_foe_onto_the_wielder() -> None:
    from kernel.world import threat

    threat._reset()
    tank = _seated("vanguard", "bram")
    dps = _seated("engineer", "cora")  # present, so the taunt must beat their threat
    nid = _aggressor()
    threat.add(nid, "cora", 40)  # the dps holds aggro first
    try:
        out = use_ability(tank, "bulwark challenge on reaver")
        assert "turns to you" in out
        present = {"bram": tank, "cora": dps}
        assert threat.top_target(nid, present) is tank  # the tank now holds the foe
        assert tank.resources["mp"].current == tank.resources["mp"].maximum - 3  # MP paid
    finally:
        threat._reset()


def test_a_taunt_needs_a_present_foe() -> None:
    tank = _seated("vanguard", "bram")
    out = use_ability(tank, "bulwark challenge")  # no target
    assert "on whom?" in out


def test_a_heal_generates_threat_on_engaged_foes() -> None:
    from kernel.world import threat

    threat._reset()
    healer = _seated("scholar", "cleo")
    healer.resources["hp"] = healer.resources["hp"].damage(10)
    nid = _aggressor()  # an aggressive foe shares the room
    try:
        use_ability(healer, "mend")  # a self-heal is still loud
        assert threat.score(nid, "cleo") > 0  # the healer drew aggro
    finally:
        threat._reset()


# --- buff: the support empowers an ally's blows (composes the trinity) ---------------------------


def test_a_buff_empowers_an_ally_and_spends_mp() -> None:
    tank = _seated("vanguard", "bram")
    ally = _seated("engineer", "cora")
    mp_before = tank.resources["mp"].current
    out = use_ability(tank, "rally on cora")
    assert "empowered" in out and "on Cora" in out
    assert ally.statuses["empowered"] == 3  # the buff duration
    assert tank.resources["mp"].current == mp_before - 4


def test_a_buff_on_self_empowers_the_wielder() -> None:
    tank = _seated("vanguard", "bram")
    out = use_ability(tank, "rally on me")
    assert "empowered" in out
    assert tank.statuses["empowered"] == 3


def test_a_buff_needs_a_present_ally() -> None:
    tank = _seated("vanguard", "bram")
    assert "no ally called 'ghost'" in use_ability(tank, "rally on ghost")


def test_render_abilities_shows_a_buff_targets_self_or_ally() -> None:
    tank = _seated("vanguard", "bram")
    assert "self or ally" in render_abilities(tank)
