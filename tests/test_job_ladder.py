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


def _ladder_of(jobs):
    """Rebuild the module's (_JOBS, JOBS) pair from a job list, for monkeypatching a defect in."""
    return list(jobs), {j.id: j for j in jobs}


@pytest.mark.parametrize(
    "defect, match",
    [
        # A job in the wrong tier breaks the 12/12/6 shape.
        (lambda js: [js[0]._replace(tier=2), *js[1:]], "12 / 12 / 6"),
        # A duplicate id collapses the JOBS dict below 30 while the tier shape still holds.
        (lambda js: [js[0], js[0], *js[2:]], "expected 30 jobs"),
        # An unknown role is not in the vocabulary.
        (lambda js: [js[0]._replace(primary=("Necromancer",)), *js[1:]], "unknown role"),
        # A job with no primary role.
        (lambda js: [js[0]._replace(primary=()), *js[1:]], "at least one primary"),
        # An unlock naming a job that does not exist.
        (lambda js: [*js[:12], js[12]._replace(unlock=(("ghost", 5),)), *js[13:]], "unknown job"),
        # A job requiring itself.
        (lambda js: [js[0]._replace(unlock=((js[0].id, 5),)), *js[1:]], "cannot require itself"),
        # An unlock level outside 1..30.
        (lambda js: [*js[:12], js[12]._replace(unlock=(("rogue", 0),)), *js[13:]], "out of 1-30"),
    ],
)
def test_validate_refuses_each_malformed_ladder(monkeypatch, defect, match):
    broken = defect(list(jl._JOBS))
    _jobs, _dict = _ladder_of(broken)
    monkeypatch.setattr(jl, "_JOBS", _jobs)
    monkeypatch.setattr(jl, "JOBS", _dict)
    with pytest.raises(SeedError, match=match):
        jl.validate()


def test_validate_refuses_a_schedule_that_is_not_twenty_one_slots(monkeypatch):
    monkeypatch.setattr(jl, "UNIVERSAL_PROGRESSION", [(1, ("core_trait",))])
    with pytest.raises(SeedError, match="feature slots"):
        jl.validate()


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
