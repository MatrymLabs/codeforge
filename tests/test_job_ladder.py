"""Test twin for parts/world/job_ladder.py -- the 30-job progression backbone.

Gates the Job System's structure: all 30 jobs exist across the right tiers with valid roles, every
unlock prerequisite resolves and the graph is acyclic, and the universal 21-slot schedule is intact.
The named abilities that fill those slots are later stages; this pins the backbone they hang on.
"""

import pytest

from parts.world import job_ladder as jl
from parts.world.seed import SeedError


def test_thirty_jobs_across_twelve_twelve_six_tiers():
    assert len(jl.JOBS) == 30
    assert [len(jl.tier(n)) for n in (1, 2, 3)] == [12, 12, 6]


def test_every_job_has_a_valid_primary_role():
    for job in jl.JOBS.values():
        assert job.primary, f"{job.id} has no primary role"
        for role in (*job.primary, *job.secondary):
            assert role in jl.ROLES, f"{job.id} has unknown role {role!r}"


def test_every_unlock_prerequisite_resolves_to_a_real_job_at_a_sane_level():
    for job in jl.JOBS.values():
        for req_id, req_lvl in job.unlock:
            assert req_id in jl.JOBS, f"{job.id} requires unknown job {req_id}"
            assert req_id != job.id
            assert 1 <= req_lvl <= jl.MAX_JOB_LEVEL


def test_tier_one_jobs_have_no_prerequisites():
    for job in jl.tier(1):
        assert job.unlock == (), f"Tier I job {job.id} should need no prerequisites"


def test_advanced_jobs_require_prerequisites():
    for job in (*jl.tier(2), *jl.tier(3)):
        assert job.unlock, f"advanced job {job.id} should gate behind prerequisites"


def test_the_unlock_graph_is_acyclic():
    # validate() runs the DFS at import; a circular ladder would already have raised. Re-run it
    # explicitly so this test owns the guarantee.
    jl.validate()  # raises SeedError on a cycle


def test_the_universal_schedule_grants_exactly_twenty_one_features():
    slots = jl.feature_slots()
    assert len(slots) == jl.FEATURES_PER_JOB == 21
    kinds = {slot.split("_")[0] for _lvl, slot in slots}
    # every feature family the prompt specifies appears in the schedule
    assert {"core", "active", "passive", "reaction", "support", "movement", "signature"} <= kinds
    actives = [s for _l, s in slots if s.startswith("active_")]
    assert len(actives) == 10  # ten standard actives
    assert slots[0] == (1, "core_trait") and (30, "signature") in slots


def test_unlock_checks_gate_and_report_progress():
    # A Duelist opens at Rogue 15 + Vanguard 10; below that it locks and reports what is missing.
    ready = {"rogue": 15, "vanguard": 10}
    assert jl.is_unlocked("duelist", ready)
    assert jl.missing_requirements("duelist", ready) == []
    short = {"rogue": 14, "vanguard": 10}
    assert not jl.is_unlocked("duelist", short)
    assert jl.missing_requirements("duelist", short) == [("rogue", 15)]
    # A Tier III Hexblade needs three disciplines; a fresh character misses all of them.
    assert jl.missing_requirements("hexblade", {}) == [
        ("spellblade", 20),
        ("warlock", 15),
        ("duelist", 10),
    ]


def test_a_circular_ladder_is_refused():
    # Monkeypatch a cycle into the graph and confirm the acyclic check catches it.
    import parts.world.job_ladder as mod

    original = mod.JOBS
    try:
        a = mod.Job("a", "A", 1, ("Main Tank",), (), (("b", 1),))
        b = mod.Job("b", "B", 1, ("Main Tank",), (), (("a", 1),))
        mod.JOBS = {"a": a, "b": b}
        with pytest.raises(SeedError, match="circular"):
            mod._assert_acyclic()
    finally:
        mod.JOBS = original
