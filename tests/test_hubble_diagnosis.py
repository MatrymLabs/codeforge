"""Test twin for parts/hubble/diagnosis.py -- the diagnostic decision core.

The headline guarantee is the NON-OVERRIDABLE escalation class: a security / sandbox /
retrieval-grounding failure forces `escalate` even when overall confidence is high. The four
actions (proceed / revise / escalate / stop) and the visible reasons are pinned too.
"""

from __future__ import annotations

from parts.hubble.diagnosis import (
    DiagnosticFinding,
    decide,
    render_decision,
)


def _f(dimension: str, passed: bool, weight: float = 1.0, note: str = "") -> DiagnosticFinding:
    return DiagnosticFinding(dimension, passed, weight, note)


def test_a_fully_clean_panel_proceeds() -> None:
    findings = [_f("static", True), _f("dependency", True), _f("sandbox", True)]
    d = decide(findings)
    assert d.action == "proceed" and d.confidence == 1.0


def test_low_confidence_recommends_revise() -> None:
    # A non-critical dimension fails and drags confidence below the threshold: revise, don't stop.
    findings = [_f("static", False, weight=2.0, note="lint errors"), _f("dependency", True, 1.0)]
    d = decide(findings)
    assert d.action == "revise"
    assert d.confidence < 0.75
    assert any("static" in r for r in d.reasons)


def test_a_security_failure_escalates_even_at_high_confidence() -> None:
    # THE headline case: security is one low-weight finding; everything else passes, so overall
    # confidence is high -- yet the non-overridable class forces escalate, never proceed.
    findings = [
        _f("static", True, weight=5.0),
        _f("dependency", True, weight=5.0),
        _f("security", False, weight=0.1, note="a hardcoded secret"),
    ]
    d = decide(findings)
    assert d.confidence > 0.75  # the rest of the panel looks great...
    assert d.action == "escalate"  # ...but it escalates anyway
    assert d.escalation_class == "security"


def test_a_sandbox_failure_escalates() -> None:
    d = decide([_f("static", True), _f("sandbox", False, note="dynamic test crashed")])
    assert d.action == "escalate" and d.escalation_class == "sandbox"


def test_a_retrieval_grounding_failure_escalates() -> None:
    d = decide(
        [_f("static", True), _f("retrieval_grounding", False, note="no evidence for the claim")]
    )
    assert d.action == "escalate" and d.escalation_class == "retrieval_grounding"


def test_a_total_non_critical_failure_stops() -> None:
    d = decide([_f("static", False, note="broken"), _f("dependency", False, note="unresolved")])
    assert d.action == "stop" and d.confidence == 0.0


def test_no_findings_cannot_proceed() -> None:
    d = decide([])
    assert d.action == "stop"
    assert d.reasons == ("no diagnostic evidence",)


def test_the_render_shows_findings_confidence_and_the_escalation() -> None:
    findings = [_f("static", True), _f("security", False, note="secret")]
    out = render_decision(findings, decide(findings))
    assert "HUBBLE DIAGNOSIS" in out
    assert "ESCALATE" in out
    assert "non-overridable escalation: security" in out
    assert "advisory" in out  # it advises; a human decides
