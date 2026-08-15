"""Test twin for kernel/world/callings.py -- the gate on a calling you have not yet earned.

Acceptance: a calling with no prerequisites is open to anyone; one whose prerequisites are met
opens; the verdict names the calling and carries no unmet requirements.

Refusal (fail loud): a locked calling stays locked and SAYS WHAT IS MISSING; a partially met
multi-prerequisite calling names only the parts still missing; a calling merely TOUCHED does not
count as one walked; the loader refuses a prerequisite that is negative, non-integer, self-
referential, dangling, or part of a cycle no character could ever enter.

These are the cases the Green Build Directive section 13 names among the tests that matter most:
"Calling prerequisites unlock correctly" and "locked Calling stays inaccessible". Before this
card, `prerequisite` appeared in zero test files and all 31 Aethryn callings were choosable at
level one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.world.callings import (
    CallingVerdict,
    Requirement,
    gate_calling,
    prerequisite_cycles,
    requirements_of,
)
from kernel.world.job_progress import JobProgress
from kernel.world.seed import BlueprintError, load_jobs


def _job(**requires: int) -> dict:
    return {"name": "Test Calling", "description": "", "requires": dict(requires)}


def _held(**levels: int) -> dict[str, JobProgress]:
    return {label: JobProgress(job_id=label, job_level=lvl) for label, lvl in levels.items()}


# --- acceptance -----------------------------------------------------------------------------


def test_a_calling_without_prerequisites_is_open_to_anyone() -> None:
    verdict = gate_calling("vanguard", _job(), {})
    assert verdict.open
    assert verdict.unmet == ()
    assert verdict.reason() == ""  # an open gate has nothing to explain


def test_a_met_prerequisite_opens_the_calling() -> None:
    assert gate_calling("hierophant", _job(cleric=5), _held(cleric=5)).open


def test_exceeding_a_prerequisite_still_opens_it() -> None:
    assert gate_calling("hierophant", _job(cleric=5), _held(cleric=40)).open


def test_every_prerequisite_must_be_met_not_merely_one() -> None:
    both = _job(vanguard=5, pathfinder=3)
    assert gate_calling("warden", both, _held(vanguard=5, pathfinder=3)).open
    assert not gate_calling("warden", both, _held(vanguard=5, pathfinder=2)).open


# --- refusal: the locked calling stays locked, and says why ---------------------------------


def test_a_locked_calling_is_refused() -> None:
    verdict = gate_calling("hierophant", _job(cleric=5), {})
    assert not verdict.open
    assert verdict.unmet == (Requirement("cleric", 5),)


def test_the_refusal_names_what_is_missing() -> None:
    # A refusal that cannot say what is missing is a wall, not a gate.
    reason = gate_calling("hierophant", _job(cleric=5), _held(cleric=2)).reason()
    assert "cleric" in reason and "5" in reason


def test_the_refusal_uses_display_names_when_given_them() -> None:
    reason = gate_calling("hierophant", _job(cleric=5), {}).reason({"cleric": "Cleric"})
    assert "Cleric at level 5" in reason


def test_only_the_unmet_parts_are_named() -> None:
    verdict = gate_calling("warden", _job(vanguard=5, pathfinder=3), _held(vanguard=9))
    assert verdict.unmet == (Requirement("pathfinder", 3),)
    assert "vanguard" not in verdict.reason()  # do not scold a player for what they have done


def test_touching_a_calling_is_not_walking_it() -> None:
    """Opening a record by taking a job for one moment must not satisfy a requirement.

    bind_calling opens a JobProgress at level 1, so if 'has a record' counted, a player could
    unlock an advanced calling by taking and dropping its prerequisite in two commands.
    """
    assert not gate_calling("hierophant", _job(cleric=5), _held(cleric=1)).open


def test_a_calling_never_walked_counts_as_zero_not_one() -> None:
    assert gate_calling("x", _job(cleric=1), {}).unmet == (Requirement("cleric", 1),)


def test_requirements_are_ordered_so_output_never_shuffles() -> None:
    assert requirements_of(_job(zeta=1, alpha=2)) == (
        Requirement("alpha", 2),
        Requirement("zeta", 1),
    )


def test_a_verdict_is_not_a_boolean() -> None:
    # Guards the style rule: a caller must not be able to render "no" as silence.
    assert isinstance(gate_calling("x", _job(a=2), {}), CallingVerdict)


# --- refusal: the loader refuses content that could never be played -------------------------


def _seed(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "jobs.yaml"
    path.write_text(body, encoding="utf-8")
    return path


BASE = """
vanguard:
  name: Vanguard
  description: a first path
  stats: {strength: 10}
"""


def test_the_loader_refuses_a_prerequisite_on_an_unknown_calling(tmp_path: Path) -> None:
    path = _seed(
        tmp_path,
        BASE
        + """
warden:
  name: Warden
  description: advanced
  stats: {strength: 10}
  requires: {nosuchcalling: 3}
""",
    )
    with pytest.raises(BlueprintError, match="unknown calling"):
        load_jobs(path)


def test_the_loader_refuses_a_calling_that_requires_itself(tmp_path: Path) -> None:
    path = _seed(
        tmp_path,
        BASE
        + """
warden:
  name: Warden
  description: advanced
  stats: {strength: 10}
  requires: {warden: 2}
""",
    )
    with pytest.raises(BlueprintError, match="cannot require itself"):
        load_jobs(path)


def test_the_loader_refuses_a_cycle_no_character_could_enter(tmp_path: Path) -> None:
    """Two callings requiring each other are both unreachable forever.

    That is a content defect, and it fails at load rather than becoming a mystery a player
    discovers by failing indefinitely.
    """
    path = _seed(
        tmp_path,
        BASE
        + """
warden:
  name: Warden
  description: advanced
  stats: {strength: 10}
  requires: {reaver: 2}
reaver:
  name: Reaver
  description: advanced
  stats: {strength: 10}
  requires: {warden: 2}
""",
    )
    with pytest.raises(BlueprintError, match="cycle"):
        load_jobs(path)


@pytest.mark.parametrize("bad", ["0", "-3", "'five'", "true"])
def test_the_loader_refuses_a_level_that_is_not_a_real_rank(tmp_path: Path, bad: str) -> None:
    path = _seed(
        tmp_path,
        BASE
        + f"""
warden:
  name: Warden
  description: advanced
  stats: {{strength: 10}}
  requires: {{vanguard: {bad}}}
""",
    )
    with pytest.raises(BlueprintError):
        load_jobs(path)


def test_a_seed_without_any_prerequisites_still_loads(tmp_path: Path) -> None:
    # Additive schema: adding this gate locked nothing that was previously open.
    jobs = load_jobs(_seed(tmp_path, BASE))
    assert jobs["vanguard"]["requires"] == {}


# --- the cycle finder itself ----------------------------------------------------------------


def test_a_clean_graph_reports_no_cycles() -> None:
    assert prerequisite_cycles({"a": _job(), "b": _job(a=2), "c": _job(b=2)}) == []


def test_a_cycle_is_reported_once_not_once_per_rotation() -> None:
    found = prerequisite_cycles({"a": _job(b=1), "b": _job(a=1)})
    assert len(found) == 1
    assert set(found[0]) == {"a", "b"}


def test_a_dangling_reference_is_not_mistaken_for_a_cycle() -> None:
    # The loader names a dangling reference separately, with a clearer message.
    assert prerequisite_cycles({"a": _job(ghost=1)}) == []


# --- the shipped Aethryn content ------------------------------------------------------------


def test_the_aethryn_seed_actually_gates_its_advanced_callings() -> None:
    """The mechanism is worth nothing if no shipped calling uses it."""
    jobs = load_jobs(Path("content/seeds/aethryn/jobs.yaml"))
    gated = {label: job["requires"] for label, job in jobs.items() if job["requires"]}
    assert gated, "no Aethryn calling declares a prerequisite"
    for label, requires in gated.items():
        for needed in requires:
            assert needed in jobs, f"{label} requires missing calling {needed}"


def test_the_three_first_paths_stay_open_to_a_new_character() -> None:
    jobs = load_jobs(Path("content/seeds/aethryn/jobs.yaml"))
    for first in ("vanguard", "pathfinder", "emberwright"):
        assert gate_calling(first, jobs[first], {}).open, (
            f"{first} must be open at character creation"
        )


# --- the engine tick: a feature is not wired until handle_command proves it reachable ---------


def _gated_seed(monkeypatch) -> None:
    """Give the running seed one advanced calling, so the tick can be driven against it.

    The default seed (first-forge) ships four foundational callings and no prerequisites, which
    is correct for it. Injecting here keeps this test about REACHABILITY THROUGH THE TICK rather
    than about which callings Aethryn happens to gate today.
    """
    import forge
    from kernel.world import jobs as jobs_card

    gated = dict(jobs_card.JOBS)
    gated["warden"] = {
        **jobs_card.JOBS["vanguard"],
        "name": "Warden",
        "description": "an advanced path",
        "requires": {"vanguard": 5},
    }
    # forge.py imports JOBS directly, so it holds its OWN reference to the mapping. Patching only
    # the card leaves the tick's announce path reading the original, which is how the first run of
    # this test died with KeyError: 'warden'. Both references move together.
    monkeypatch.setattr(jobs_card, "JOBS", gated)
    monkeypatch.setattr(forge, "JOBS", gated, raising=False)


def test_the_tick_refuses_a_locked_calling(monkeypatch) -> None:
    from forge import handle_command
    from kernel.world.session import Session

    _gated_seed(monkeypatch)
    s = Session(player_id="matrym")
    out = handle_command(s, "job warden")
    assert "not yet open" in out
    assert "Vanguard at level 5" in out  # the road is named, not merely refused
    assert s.job == "", "a refused calling must not bind: authority before capability"
    assert s.stats is None, "no stats may be born from a calling that was refused"


def test_the_tick_opens_the_calling_once_the_road_is_walked(monkeypatch) -> None:
    from forge import handle_command
    from kernel.world.job_progress import JobProgress
    from kernel.world.session import Session

    _gated_seed(monkeypatch)
    s = Session(player_id="matrym")
    s.job_progress["vanguard"] = JobProgress(job_id="vanguard", job_level=5)
    out = handle_command(s, "job warden")
    assert "way of the Warden" in out
    assert s.job == "warden"


def test_the_tick_lists_a_locked_calling_with_its_price(monkeypatch) -> None:
    from forge import handle_command
    from kernel.world.session import Session

    _gated_seed(monkeypatch)
    out = handle_command(Session(player_id="matrym"), "jobs")
    assert "warden" in out
    assert "LOCKED" in out, "a road you cannot see is not a goal"


def test_the_secondary_slot_is_not_an_open_window(monkeypatch) -> None:
    """The lock must hold on every door into a calling, not just the front one."""
    from forge import handle_command
    from kernel.world.session import Session

    _gated_seed(monkeypatch)
    s = Session(player_id="matrym")
    handle_command(s, "job vanguard")
    out = handle_command(s, "secondary warden")
    assert "not yet open" in out
    assert s.secondary_job == ""
