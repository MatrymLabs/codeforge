"""Test twin for parts/qualitygate.py -- the Safety + QA spine.

Acceptance (a complete object passes, the self-audit runs over the real registry,
an admin object is rated higher risk) and refusal (a built object missing its file
fails, a prototype is exempt, an unknown object is handled) are both pinned.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from forge import handle_command
from parts.qualitygate import (
    FAIL,
    PASS,
    docs_check,
    gate_all,
    run_gate,
    safety_review,
)
from parts.registry import Designation
from parts.session import SESSIONS, Session


def _rec(designation: str = "PRT-05.001", **over: object) -> Designation:
    base: dict[str, object] = dict(
        designation=designation,
        name="a part",
        status="active",
        function="does a thing",
        label="thing",
        file="parts/registry.py",  # a real file, so QG02 passes
        tests="tests/test_registry.py",  # a real test, so QG03 passes
    )
    base.update(over)
    return Designation(**base)  # type: ignore[arg-type]


# --- QualityGate --------------------------------------------------------------


def test_a_complete_object_passes() -> None:
    result = run_gate(_rec(notes="documented inline"))
    assert result.verdict == PASS
    assert all(c.result != FAIL for c in result.checks)


def test_run_gate_honors_the_shared_stat_cache() -> None:
    # EXP-002: run_gate reads path existence from the shared memo instead of re-stat'ing.
    # Pre-seed the cache with a lie (the real file DOES exist) and prove the gate trusts it,
    # which proves the memo is consulted and duplicate stats are eliminated.
    rec = _rec()  # file=parts/registry.py, tests=tests/test_registry.py (both real)
    cache = {rec.file: False, rec.tests: False}
    result = run_gate(rec, stat_cache=cache)
    qg02 = next(c for c in result.checks if c.check_id == "QG02")
    qg05 = next(c for c in result.checks if c.check_id == "QG05")
    assert qg02.result == FAIL  # honored the cache (did not re-stat the real file)
    assert qg05.result == FAIL  # QG05 reused the same memoized answer, no duplicate stat


def test_gate_all_stats_each_path_once(monkeypatch: pytest.MonkeyPatch) -> None:
    # The whole self-audit stats any given proof path at most once, across all records and
    # across QG02/QG03/QG05 (which previously re-checked file+tests).
    from pathlib import Path as _P

    seen: list[str] = []
    real_exists = _P.exists

    def counting_exists(self: _P) -> bool:
        seen.append(str(self))
        return real_exists(self)

    monkeypatch.setattr(_P, "exists", counting_exists)
    records = [_rec("PRT-05.001"), _rec("PRT-05.002")]
    gate_all(records)
    # Two records x {file, tests} = 2 distinct paths; each stat'ed once despite QG02/03/05.
    assert len(seen) == len(set(seen)), f"a path was stat'ed more than once: {seen}"


def test_a_built_object_missing_its_file_fails() -> None:
    result = run_gate(_rec(file="parts/ghost.py"))
    assert result.verdict == FAIL
    assert any(c.check_id == "QG02" and c.result == FAIL for c in result.checks)


def test_a_prototype_is_exempt_from_file_and_test_checks() -> None:
    result = run_gate(_rec("RM-02.001", status="prototype", file="seeds/haven-city.yaml"))
    assert result.verdict in (PASS, "watch")  # never a hard fail for not-yet-built
    q2 = next(c for c in result.checks if c.check_id == "QG02")
    assert q2.result == "n/a"


def test_active_without_tests_flags_maturity_honesty() -> None:
    result = run_gate(_rec(tests=""))  # declared active but no tests filed
    assert result.verdict == FAIL
    assert any(c.check_id == "QG05" and c.result == FAIL for c in result.checks)


def test_gate_all_audits_the_real_registry() -> None:
    results = gate_all()  # composes with the real registry -- the proof of concept
    assert len(results) >= 20  # rooms + commands + items are filed
    assert all(r.verdict in (PASS, "watch", FAIL) for r in results)


def test_the_shipped_board_has_no_failures() -> None:
    # The growth gate (hard bar): no filed object may be `active` without a file + tests
    # -- that would be a FAIL. A missing docs link is only a soft `watch`. So a red board
    # means an untested/unfiled active object slipped in; CI must catch it here.
    from parts.registry import load_collective

    fails = [r.designation for r in gate_all(load_collective()) if r.verdict == FAIL]
    assert not fails, f"QA board has failures (untested/unfiled active objects): {fails}"


# --- SafetyReview -------------------------------------------------------------


def test_an_admin_command_is_rated_higher_risk() -> None:
    finding = safety_review(_rec("CMD-04.001", label="@sg", tags=["command", "admin"]))
    assert finding.risk_level == "medium"
    assert finding.approval_required is True
    assert "unsafe_command_execution" in finding.categories


def test_a_read_only_object_is_low_risk() -> None:
    finding = safety_review(_rec("RM-01.001", label="workshop"))
    assert finding.risk_level == "low"
    assert finding.approval_required is False


def test_safety_review_flags_item_and_prototype_branches() -> None:
    item = safety_review(_rec("ITM-04.001", label="excalibur"))
    assert "broken_player_progression" in item.categories
    proto = safety_review(_rec("RM-02.001", status="prototype", label="city"))
    assert "untested_behavior" in proto.categories


def test_render_paths_handle_an_unknown_designation() -> None:
    from parts.qualitygate import render_gate, render_safety

    assert "No object" in render_gate("RM-09.999")
    assert "No object" in render_safety("RM-09.999")


# --- DocumentationImpactSweep -------------------------------------------------


def test_docs_check_reports_presence(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("x")
    out = docs_check(root=tmp_path)
    assert "README.md" in out
    assert "MISSING" in out  # the others aren't in the temp root


# --- reachable through the engine tick ---------------------------------------


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _player() -> Session:
    session = Session(player_id="auditor")
    SESSIONS["auditor"] = session
    return session


def test_qa_gate_all_through_the_tick() -> None:
    out = handle_command(_player(), "qa gate all")
    assert "qa gate all" in out.lower()
    assert "audited" in out


def test_qa_gate_one_through_the_tick() -> None:
    out = handle_command(_player(), "qa gate RM-03.002")
    assert "QualityGate" in out
    assert "Verdict" in out


def test_safety_review_through_the_tick() -> None:
    out = handle_command(_player(), "safety review CMD-04.001")
    assert "SafetyReview" in out
    assert "Risk level" in out


def test_docs_check_through_the_tick() -> None:
    assert "Documentation Impact Sweep" in handle_command(_player(), "docs check")
