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


def _rec(designation: str = "PRT-UM05-S01-N001-001-R0", **over: object) -> Designation:
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


def test_a_built_object_missing_its_file_fails() -> None:
    result = run_gate(_rec(file="parts/ghost.py"))
    assert result.verdict == FAIL
    assert any(c.check_id == "QG02" and c.result == FAIL for c in result.checks)


def test_a_prototype_is_exempt_from_file_and_test_checks() -> None:
    result = run_gate(
        _rec("RM-UM02-S01-N001-001-R0", status="prototype", file="seeds/haven-city.yaml")
    )
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


# --- SafetyReview -------------------------------------------------------------


def test_an_admin_command_is_rated_higher_risk() -> None:
    finding = safety_review(
        _rec("CMD-UM04-S01-N001-001-R0", label="@sg", tags=["command", "admin"])
    )
    assert finding.risk_level == "medium"
    assert finding.approval_required is True
    assert "unsafe_command_execution" in finding.categories


def test_a_read_only_object_is_low_risk() -> None:
    finding = safety_review(_rec("RM-UM01-S01-N001-001-R0", label="workshop"))
    assert finding.risk_level == "low"
    assert finding.approval_required is False


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
    out = handle_command(_player(), "qa gate RM-UM03-S01-N001-002-R0")
    assert "QualityGate" in out
    assert "Verdict" in out


def test_safety_review_through_the_tick() -> None:
    out = handle_command(_player(), "safety review CMD-UM04-S01-N001-001-R0")
    assert "SafetyReview" in out
    assert "Risk level" in out


def test_docs_check_through_the_tick() -> None:
    assert "Documentation Impact Sweep" in handle_command(_player(), "docs check")
