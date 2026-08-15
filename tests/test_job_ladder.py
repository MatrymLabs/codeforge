"""Test twin for kernel/world/job_ladder.py -- the playable job roster + each calling's kit.

Gates the one job-system invariant: every playable calling is a real job that ships with a real
ability kit (so a new character can always pick a class and fight), and the module is the single
source of the per-job level cap. Covers the active seed (first-forge, the default), the flagship
aethryn roster directly, and the fail-loud refusal of an unarmed calling.
"""

from pathlib import Path

import pytest

from kernel.world import job_ladder as jl
from kernel.world.seed import BlueprintError, load_abilities, load_jobs


def test_the_roster_is_the_active_seeds_callings_and_every_one_is_armed():
    assert jl.roster()  # the booted world has playable callings
    for calling in jl.roster():
        assert jl.is_calling(calling)
        assert jl.is_armed(calling), f"calling {calling!r} ships with no ability kit"


def test_kit_returns_a_callings_real_moveset():
    # first-forge (the default test seed): the Vanguard wields Power Strike.
    assert "power_strike" in jl.kit("vanguard")
    assert jl.kit("engineer")  # the engineer is armed too
    assert jl.kit("not_a_calling") == []  # a non-calling has no kit here


def test_validate_passes_for_the_shipped_roster():
    jl.validate()  # every calling is armed; no raise


def test_the_cap_is_the_single_source_of_the_job_level_ceiling():
    assert jl.MAX_JOB_LEVEL == 30
    from kernel.world import progression

    assert progression.JP_TRACK[2] == jl.MAX_JOB_LEVEL  # progression reads the cap from here


def test_an_unarmed_calling_fails_loud(monkeypatch):
    # a calling with no ability declared anywhere must be caught at validate().
    roster = dict(jl.CALLINGS)
    roster["ghostwright"] = {"name": "Ghostwright", "description": "d", "stats": {}}
    monkeypatch.setattr(jl, "CALLINGS", roster)
    with pytest.raises(BlueprintError, match="no ability kit.*ghostwright"):
        jl.validate()


def test_every_aethryn_calling_ships_a_kit():
    # the flagship: all 30 callings are armed (loaded directly, independent of the booted seed).
    aethryn = Path(__file__).resolve().parent.parent / "content" / "blueprints" / "aethryn"
    callings = set(load_jobs(aethryn / "jobs.yaml"))
    abilities = load_abilities(aethryn / "abilities.yaml")
    armed = {job for ability in abilities.values() for job in ability["jobs"]}
    assert len(callings) == 30
    assert callings <= armed, f"unarmed aethryn callings: {sorted(callings - armed)}"
