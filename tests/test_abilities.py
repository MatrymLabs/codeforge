"""Test twin for parts/world/abilities.py + seed.load_abilities -- usable combat moves.

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
from parts.world import npcs
from parts.world.abilities import abilities_for, render_abilities, use_ability
from parts.world.seed import SeedError, load_abilities
from parts.world.session import Session


@pytest.fixture(autouse=True)
def fresh_npcs():
    """Snapshot the NPC table (combat mutates the dummy's hp) and restore it after each test."""
    snap = copy.deepcopy(npcs.NPCS)
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(snap)


def _at_dummy(job: str) -> Session:
    """A session with `job`, standing in the courtyard where the training dummy waits."""
    s = Session(player_id="hero")
    forge.handle_command(s, f"job {job}")
    forge.handle_command(s, "go north")  # forge -> courtyard (the dummy's room)
    return s


# --- the ability data maps jobs correctly (first-forge seed) -------------------------------------


def test_abilities_map_to_the_jobs_that_declare_them() -> None:
    assert [a["name"] for _, a in abilities_for("scholar")] == ["Arcane Bolt", "Mend"]
    assert [a["name"] for _, a in abilities_for("vanguard")] == ["Power Strike"]
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


def test_a_heal_ability_restores_hp_and_costs_mp() -> None:
    s = _at_dummy("scholar")
    s.resources["hp"] = s.resources["hp"].damage(10)
    hp_before, mp_before = s.resources["hp"].current, s.resources["mp"].current
    out = use_ability(s, "mend")
    assert "Mend" in out and "recover" in out
    assert s.resources["hp"].current > hp_before
    assert s.resources["mp"].current == mp_before - 5


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
    seeds = Path(__file__).resolve().parent.parent / "seeds"
    files = sorted(seeds.glob("*/abilities.yaml"))
    assert files  # at least first-forge ships one
    for f in files:
        assert load_abilities(f)  # non-empty and well-formed


def test_aethryn_ships_a_moveset_for_each_calling() -> None:
    seeds = Path(__file__).resolve().parent.parent / "seeds"
    ab = load_abilities(seeds / "aethryn" / "abilities.yaml")
    wielders = {job for a in ab.values() for job in a["jobs"]}
    assert wielders == {"vanguard", "pathfinder", "emberwright"}  # every aethryn calling armed


def test_load_abilities_accepts_a_wellformed_file(tmp_path: Path) -> None:
    p = _abilities_file(
        tmp_path,
        "jab:\n  name: Jab\n  kind: strike\n  power: 4\n"
        "  scales: strength\n  mp_cost: 2\n  jobs: [vanguard]\n",
    )
    loaded = load_abilities(p)
    assert loaded["jab"]["name"] == "Jab" and loaded["jab"]["scales"] == "strength"


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
        ("bad:\n  kind: explode\n  jobs: [vanguard]\n", "must be 'strike' or 'heal'"),
        (
            "bad:\n  kind: strike\n  scales: charisma\n  jobs: [vanguard]\n",
            "'scales' must be an attribute",
        ),
        (
            "bad:\n  kind: strike\n  power: -3\n  jobs: [vanguard]\n",
            "'power' must be a non-negative",
        ),
    ],
)
def test_load_abilities_refuses_a_malformed_ability(tmp_path: Path, body: str, match: str) -> None:
    with pytest.raises(SeedError, match=match):
        load_abilities(_abilities_file(tmp_path, body))
