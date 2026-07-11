"""Test twin for the Stewardship Gate (parts/stewardship/*).

Acceptance: a clean, disclosed, low-risk change is eligible and NOT over-taxed. Refusal (each
FWA failure mode): failing tests, SAST findings, secrets, an unadmitted dependency, undisclosed
AI, and an under-reviewed high-risk change each block. Governance: risk tracks the surface a
change touches, and nothing is ever auto-merged.
"""

from __future__ import annotations

from parts.stewardship.change import ChangeDescriptor
from parts.stewardship.gate import blocking_reasons, render_verdict, verify_change
from parts.stewardship.risk import assess_risk


def _clean(**over: object) -> ChangeDescriptor:
    base: dict[str, object] = dict(
        change_id="chg-001",
        title="tidy a docstring",
        files_touched=("parts/score_sheet.py",),
        ai_assisted=False,
        tests_passed=True,
        sast_blocking_findings=0,
        secrets_findings=0,
        dependencies_added=(),
        dependencies_approved=True,
        human_approvals=0,
    )
    base.update(over)
    return ChangeDescriptor(**base)  # type: ignore[arg-type]


def test_a_clean_low_risk_disclosed_change_is_eligible_and_untaxed() -> None:
    v = verify_change(_clean())
    assert v.eligible
    assert v.risk.tier == "low" and v.required_approvals == 0  # low risk is not taxed
    assert all(c.status == "pass" for c in v.checks)


def test_undisclosed_ai_blocks() -> None:
    v = verify_change(_clean(ai_assisted=None))  # None = undisclosed
    assert not v.eligible
    assert any(r.startswith("FWA05") for r in blocking_reasons(v))


def test_failing_tests_block() -> None:
    v = verify_change(_clean(tests_passed=False))
    assert not v.eligible and any(r.startswith("FWA01") for r in blocking_reasons(v))


def test_static_analysis_findings_block() -> None:
    v = verify_change(_clean(sast_blocking_findings=2))
    assert not v.eligible and any(r.startswith("FWA02") for r in blocking_reasons(v))


def test_secrets_block() -> None:
    v = verify_change(_clean(secrets_findings=1))
    assert not v.eligible and any(r.startswith("FWA03") for r in blocking_reasons(v))


def test_an_unadmitted_dependency_blocks() -> None:
    v = verify_change(_clean(dependencies_added=("leftpad",), dependencies_approved=False))
    assert not v.eligible and any(r.startswith("FWA04") for r in blocking_reasons(v))
    # ... and an ADMITTED dependency passes that check.
    ok = verify_change(_clean(dependencies_added=("leftpad",), dependencies_approved=True))
    assert not any(r.startswith("FWA04") for r in blocking_reasons(ok))


def test_risk_tracks_the_security_surface_touched() -> None:
    # A change to auth code + a new dependency, AI-authored, is high risk (report's warning:
    # AI PRs can look small while touching security-critical surfaces).
    risky = _clean(
        files_touched=("parts/accounts.py",),
        ai_assisted=True,
        dependencies_added=("some-pkg",),
        dependencies_approved=True,
    )
    a = assess_risk(risky)
    assert a.tier == "high" and a.required_approvals == 2
    assert any("security surface" in f for f in a.factors)


def test_a_high_risk_change_needs_more_approvals() -> None:
    risky = dict(
        files_touched=(".github/workflows/ci.yml",),
        ai_assisted=True,
        dependencies_added=("some-pkg",),
        dependencies_approved=True,
    )
    blocked = verify_change(_clean(human_approvals=1, **risky))  # high risk, only 1 approval
    assert not blocked.eligible and any(r.startswith("FWA06") for r in blocking_reasons(blocked))
    passed = verify_change(_clean(human_approvals=2, **risky))  # enough scrutiny
    assert passed.eligible


def test_the_report_shows_checks_risk_and_that_nothing_auto_merges() -> None:
    out = render_verdict(verify_change(_clean(tests_passed=False)))
    assert "STEWARDSHIP GATE" in out
    assert "CHECKS" in out and "FWA01" in out
    assert "BLOCKED" in out
    assert "auto-merge" in out  # the verdict advises; it never merges


def test_the_report_lists_the_risk_factors_that_fired() -> None:
    # A risky change renders its visible risk factors (the score never hides its reasons).
    out = render_verdict(
        verify_change(_clean(files_touched=("parts/accounts.py",), human_approvals=1))
    )
    assert "risk: MEDIUM" in out or "risk: HIGH" in out
    assert "security surface" in out  # the factor line is shown
