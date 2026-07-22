"""Test twin for parts/change_ledger.py -- a gated change lifecycle composed from five parts."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.change_ledger import ChangeLedger, _arc_clear, _tests_passed
from parts.repository import DuplicateKey
from parts.shelf.statemachine import Fired, Refusal
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
    led.advance("PF-1", "canary", actor="operator")
    led.record_arc("PF-1", "watchlist")  # slice 4: deploy needs a non-blocked ARC verdict
    for event, actor in [
        ("deploy", "operator"),
        ("verify", "operator"),
        ("close", "*"),
    ]:
        led.advance("PF-1", event, actor=actor)
    assert led.status("PF-1") == "closed"
    assert [h["event"] for h in led.history("PF-1")][:3] == ["triage", "approve", "build"]


def _to_canary(led: ChangeLedger) -> None:
    """Walk PF-1 to canary (tests passing), ready for the deploy gate."""
    led.advance("PF-1", "triage")
    led.advance("PF-1", "approve", actor="approver")
    led.advance("PF-1", "build")
    led.advance("PF-1", "test")
    led.record_test("PF-1", "ci")
    led.advance("PF-1", "canary", actor="operator")


def test_a_change_cannot_deploy_without_an_arc_verdict():
    led = _opened()
    _to_canary(led)
    blocked = led.advance("PF-1", "deploy", actor="operator")  # no ARC recorded
    assert isinstance(blocked, Refusal) and "no ARC verdict" in blocked.reason


def test_a_blocked_arc_verdict_stops_deploy():
    led = _opened()
    _to_canary(led)
    led.record_arc("PF-1", "blocked")
    blocked = led.advance("PF-1", "deploy", actor="operator")
    assert isinstance(blocked, Refusal) and "blocked" in blocked.reason


def test_a_non_blocked_arc_verdict_lets_it_deploy():
    led = _opened()
    _to_canary(led)
    led.record_arc("PF-1", "watchlist")  # not ready, but not blocked -> allowed
    assert isinstance(led.advance("PF-1", "deploy", actor="operator"), Fired)
    assert led.get("PF-1").arc_verdict == "watchlist"


def test_record_arc_refuses_an_unknown_verdict():
    led = _opened()
    with pytest.raises(ValueError):
        led.record_arc("PF-1", "green")


def test_guards_refuse_a_context_without_a_change():
    # A broken ctx never crashes the tick; the guard refuses cleanly.
    assert _tests_passed({}) == "no change in context"
    assert _arc_clear({}) == "no change in context"


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


# --- arc_status(): the pure mapping the ARC evidence driver reads --------------


def test_arc_status_of_an_empty_ledger_is_missing():
    assert _ledger().arc_status()[0] == "missing"  # nothing tracked, never a pass


def test_arc_status_watchlists_a_change_in_flight():
    led = _opened()  # PF-1 sits at 'identified' (non-terminal)
    status, detail = led.arc_status()
    assert status == "watchlist" and "1 open" in detail


def test_arc_status_blocks_a_rolled_back_change():
    led = _opened()
    led.advance("PF-1", "triage")
    led.advance("PF-1", "approve", actor="approver")
    led.advance("PF-1", "build")
    led.advance("PF-1", "test")
    led.advance("PF-1", "fail")  # testing -> rolled_back
    assert led.status("PF-1") == "rolled_back"
    assert led.arc_status()[0] == "blocked"


def test_arc_status_is_ready_when_every_change_reached_a_clean_terminal():
    led = _opened()
    for event, actor in [("triage", "*"), ("approve", "approver"), ("build", "*"), ("test", "*")]:
        led.advance("PF-1", event, actor=actor)
    led.record_test("PF-1", "ci")
    led.advance("PF-1", "canary", actor="operator")
    led.record_arc("PF-1", "watchlist")
    for event, actor in [("deploy", "operator"), ("verify", "operator"), ("close", "*")]:
        led.advance("PF-1", event, actor=actor)
    assert led.status("PF-1") == "closed"
    assert led.arc_status()[0] == "ready"
