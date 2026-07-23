"""Test twin for parts/retention.py -- hold-aware retention analysis (read-only R1).

Acceptance: age is computed from the record stamp; a record past its kind's period is eligible; a
hold covers by 'all' / kind / 'subject:<prefix>'; plan() partitions active / hold-blocked /
candidate; the doctor renders honestly; loaders default sanely and read a YAML override. Refusal:
a real (non-dry-run) disposition refuses in R1, and a malformed policy/hold fails loud. Every test
uses tmp_path / injected data, so the real (git-tracked) chronicle/ dir is never touched.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from parts.chronicle import Record, record_incident, record_metric
from parts.retention import (
    DEFAULT_POLICY,
    Hold,
    RetentionError,
    RetentionRule,
    dispose,
    held,
    is_eligible,
    load_holds,
    load_policy,
    plan,
    record_age_days,
    render_doctor,
)

_TODAY = date(2026, 7, 14)


def _metric(name: str, when: datetime, root: Path) -> Record:
    return record_metric(name, 1.0, commit="c", root=root, stamp=when)


def test_record_age_days_counts_from_the_stamp() -> None:
    r = Record("metric", {"name": "m", "value": 1}, "c", "2026-07-04T00:00:00Z", "", "h")
    assert record_age_days(r, _TODAY) == 10


def test_a_record_past_its_period_is_eligible(tmp_path: Path) -> None:
    old = _metric("old", datetime(2016, 1, 1, tzinfo=UTC), tmp_path)  # ancient
    new = _metric("new", datetime(2026, 7, 1, tzinfo=UTC), tmp_path)  # recent
    assert is_eligible(old, DEFAULT_POLICY, _TODAY) is True
    assert is_eligible(new, DEFAULT_POLICY, _TODAY) is False


def test_a_kind_with_no_policy_is_never_eligible() -> None:
    ancient = Record("metric", {"name": "m", "value": 1}, "c", "2000-01-01T00:00:00Z", "", "h")
    assert is_eligible(ancient, {}, _TODAY) is False  # empty policy -> keep


def test_a_hold_covers_by_all_kind_and_subject() -> None:
    rec = Record(
        "ai-eval",
        {"subject": "arch.q1", "score": 1, "model": "m", "passed": True},
        "c",
        "2020-01-01T00:00:00Z",
        "",
        "h",
    )
    assert Hold("all", "x").covers(rec) is True
    assert Hold("ai-eval", "x").covers(rec) is True
    assert Hold("subject:arch.", "x").covers(rec) is True
    assert Hold("metric", "x").covers(rec) is False
    assert Hold("subject:other", "x").covers(rec) is False


def test_held_returns_the_first_covering_hold() -> None:
    rec = Record(
        "incident",
        {"what": "x", "severity": "high", "status": "open"},
        "c",
        "2016-01-01T00:00:00Z",
        "",
        "h",
    )
    assert held(rec, []) is None
    match = held(rec, [Hold("metric", "no"), Hold("incident", "yes")])
    assert match is not None and match.reason == "yes"


def test_plan_partitions_active_blocked_and_candidate(tmp_path: Path) -> None:
    old = _metric("old", datetime(2016, 1, 1, tzinfo=UTC), tmp_path)
    new = _metric("new", datetime(2026, 7, 1, tzinfo=UTC), tmp_path)
    ancient_incident = record_incident(
        "boom", "high", commit="c", root=tmp_path, stamp=datetime(2016, 1, 1, tzinfo=UTC)
    )
    records = [old, new, ancient_incident]
    # no holds: the two ancient records are candidates, the recent one is active
    p = plan(records, today=_TODAY)
    assert len(p.active) == 1 and len(p.candidates) == 2 and len(p.blocked) == 0
    # a hold on incidents protects the ancient incident (any hold wins)
    p2 = plan(records, holds=[Hold("incident", "litigation")], today=_TODAY)
    assert len(p2.candidates) == 1 and len(p2.blocked) == 1
    assert p2.blocked[0][1].reason == "litigation"


def test_render_doctor_shows_counts_and_the_hold_reason(tmp_path: Path) -> None:
    old = _metric("m.old", datetime(2016, 1, 1, tzinfo=UTC), tmp_path)
    out = render_doctor(plan([old], holds=[Hold("metric", "audit hold")], today=_TODAY))
    assert "RETENTION DOCTOR" in out and "any hold wins" in out
    assert "audit hold" in out and "will NOT be disposed" in out


def test_r1_refuses_a_real_disposition(tmp_path: Path) -> None:
    old = _metric("m", datetime(2016, 1, 1, tzinfo=UTC), tmp_path)
    assert dispose([old], today=_TODAY).candidates  # dry-run returns the plan
    with pytest.raises(RetentionError, match="arrives in R2"):
        dispose([old], today=_TODAY, dry_run=False)


def test_load_policy_defaults_and_reads_a_valid_override(tmp_path: Path) -> None:
    assert load_policy() == DEFAULT_POLICY  # None -> defaults
    override = tmp_path / "policy.yaml"
    override.write_text("metric:\n  period_days: 30\n  category: ops\n", encoding="utf-8")
    policy = load_policy(override)
    assert policy["metric"] == RetentionRule("metric", 30, "ops")


def test_load_policy_fails_loud_on_a_bad_period(tmp_path: Path) -> None:
    bad = tmp_path / "policy.yaml"
    bad.write_text("metric:\n  period_days: -5\n", encoding="utf-8")
    with pytest.raises(RetentionError, match="non-negative int"):
        load_policy(bad)


def test_load_holds_defaults_empty_and_fails_loud_on_a_bad_row(tmp_path: Path) -> None:
    assert load_holds() == []
    bad = tmp_path / "holds.yaml"
    bad.write_text("- scope: all\n", encoding="utf-8")  # no reason
    with pytest.raises(RetentionError, match="non-empty 'scope' and 'reason'"):
        load_holds(bad)


def test_load_holds_fails_loud_when_a_provided_path_is_missing(tmp_path: Path) -> None:
    """Safety-critical: a provided-but-missing holds file must NOT silently degrade to zero
    holds. Silent [] would let a record under a litigation/audit hold become disposition-eligible;
    'a hold always wins' must never fail open. (None still means honestly no holds.)"""
    assert load_holds(None) == []
    with pytest.raises(RetentionError, match="holds file not found"):
        load_holds(tmp_path / "moved_away.yaml")


def test_load_policy_fails_loud_when_a_provided_path_is_missing(tmp_path: Path) -> None:
    """A provided-but-missing policy path is a mistake to surface, not to hide behind defaults."""
    assert load_policy(None) == DEFAULT_POLICY
    with pytest.raises(RetentionError, match="policy file not found"):
        load_policy(tmp_path / "gone.yaml")


def test_retention_verb_reachable_through_the_engine_tick() -> None:
    from forge import handle_command
    from parts.world.session import Session

    out = handle_command(Session(player_id="matrym", location="courtyard"), "retention")
    assert "RETENTION DOCTOR" in out  # read-only doctor over the (empty in tests) Chronicle
