"""Test twin for parts/change_ledger.py -- a gated change lifecycle composed from five parts."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.change_ledger import ChangeLedger
from parts.repository import DuplicateKey
from parts.statemachine import Fired, Refusal
from parts.validation import ValidationFailed


def _ledger() -> ChangeLedger:
    return ChangeLedger()


def _opened() -> ChangeLedger:
    led = _ledger()
    led.open("PF-1", "Bump lib for CVE-2026-1", "security", "high", "ci", cve_refs=("CVE-2026-1",))
    return led


def test_opening_a_change_records_it_at_identified():
    led = _opened()
    assert led.status("PF-1") == "identified"
    change = led.get("PF-1")
    assert change is not None and change.cve_refs == ("CVE-2026-1",)


def test_intake_policy_refuses_bad_facts():
    with pytest.raises(ValidationFailed):
        _ledger().open("PF-2", "x", "not_a_kind", "high", "ci")
    with pytest.raises(ValidationFailed):
        _ledger().open("PF-3", "x", "security", "catastrophic", "ci")  # bad severity


def test_a_duplicate_change_id_is_refused():
    led = _opened()
    with pytest.raises(DuplicateKey):
        led.open("PF-1", "again", "security", "low", "ci")


def test_approval_is_role_gated():
    led = _opened()
    led.advance("PF-1", "triage")
    denied = led.advance("PF-1", "approve", actor="engineer")  # not an approver
    assert isinstance(denied, Refusal)
    assert led.status("PF-1") == "triaged"
    fired = led.advance("PF-1", "approve", actor="approver")
    assert isinstance(fired, Fired) and led.status("PF-1") == "approved"


def test_a_change_cannot_reach_canary_without_passing_tests():
    led = _opened()
    led.advance("PF-1", "triage")
    led.advance("PF-1", "approve", actor="approver")
    led.advance("PF-1", "build")
    led.advance("PF-1", "test")
    blocked = led.advance("PF-1", "canary")  # no passing evidence yet
    assert isinstance(blocked, Refusal) and "tests have not passed" in blocked.reason
    led.record_test("PF-1", "ci")  # now passing evidence exists
    assert isinstance(led.advance("PF-1", "canary"), Fired)


def test_the_full_lifecycle_reaches_closed_with_history():
    led = _opened()
    for event, actor in [
        ("triage", "*"),
        ("approve", "approver"),
        ("build", "*"),
        ("test", "*"),
    ]:
        led.advance("PF-1", event, actor=actor)
    led.record_test("PF-1", "ci")
    for event, actor in [
        ("canary", "operator"),
        ("deploy", "operator"),
        ("verify", "operator"),
        ("close", "*"),
    ]:
        led.advance("PF-1", event, actor=actor)
    assert led.status("PF-1") == "closed"
    assert [h["event"] for h in led.history("PF-1")][:3] == ["triage", "approve", "build"]


def test_an_illegal_transition_is_refused():
    led = _opened()
    assert isinstance(
        led.advance("PF-1", "deploy", actor="operator"), Refusal
    )  # can't deploy from identified


@pytest.mark.property
@given(
    events=st.lists(
        st.sampled_from(["triage", "approve", "build", "deploy", "close", "junk"]), max_size=15
    )
)
def test_only_legal_transitions_ever_change_state(events):
    led = _opened()
    for event in events:
        before = led.status("PF-1")
        outcome = led.advance("PF-1", event, actor="approver")
        after = led.status("PF-1")
        # state changes only on a Fired outcome; a Refusal never moves it
        assert (after != before) == isinstance(outcome, Fired)
