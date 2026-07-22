"""Test twin for parts/shelf/test_evidence.py -- honest evidence: missing is never a pass."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.shelf.test_evidence import (
    ERROR,
    FAILED,
    PASSED,
    EvidenceError,
    EvidenceLedger,
)


def test_all_passed_evidence_reports_passed():
    led = EvidenceLedger(environment="ci", commit="abc123")
    led.expect("a")
    led.expect("b")
    led.record("a", PASSED)
    led.record("b", PASSED)
    assert led.passed() is True


def test_records_carry_the_environment_and_commit():
    led = EvidenceLedger(environment="ci", commit="abc123")
    led.record("a", PASSED)
    ev = led.results()[0]
    assert ev.environment == "ci" and ev.commit == "abc123"


def test_an_expected_but_unrecorded_check_is_missing_and_not_a_pass():
    led = EvidenceLedger()
    led.expect("a")
    led.expect("b")
    led.record("a", PASSED)
    statuses = {e.check_id: e.status for e in led.results()}
    assert statuses["b"] == "missing"
    assert led.passed() is False  # missing evidence can never be a pass


def test_an_empty_ledger_is_not_a_pass():
    assert EvidenceLedger().passed() is False


def test_a_runner_error_is_distinct_from_a_test_failure():
    led = EvidenceLedger()
    led.record("a", ERROR)
    led.record("b", FAILED)
    statuses = {e.check_id: e.status for e in led.results()}
    assert statuses == {"a": ERROR, "b": FAILED}
    assert led.passed() is False


def test_an_unrecordable_status_fails_loud():
    with pytest.raises(EvidenceError):
        EvidenceLedger().record("a", "missing")  # missing is derived, never recorded


def test_gaps_lists_everything_not_passed():
    led = EvidenceLedger()
    led.expect("missing_one")
    led.record("failed_one", FAILED)
    led.record("ok", PASSED)
    assert {e.check_id for e in led.gaps()} == {"missing_one", "failed_one"}


@pytest.mark.property
@given(statuses=st.lists(st.sampled_from([PASSED, FAILED, ERROR]), min_size=1, max_size=15))
def test_passed_is_true_iff_every_recorded_check_passed(statuses):
    led = EvidenceLedger()
    for i, s in enumerate(statuses):
        led.record(f"c{i}", s)
    assert led.passed() == all(s == PASSED for s in statuses)


# --- arc_status(): the pure mapping ARC reads (acceptance + refusal) ----------


def test_arc_status_of_an_empty_ledger_is_missing():
    assert EvidenceLedger().arc_status()[0] == "missing"  # nothing recorded, never a pass


def test_arc_status_is_ready_when_every_check_passed():
    led = EvidenceLedger()
    led.record("a", PASSED)
    led.record("b", PASSED)
    assert led.arc_status()[0] == "ready"


def test_arc_status_blocks_on_a_failed_or_errored_check():
    failed = EvidenceLedger()
    failed.record("a", PASSED)
    failed.record("b", FAILED)
    assert failed.arc_status()[0] == "blocked"
    errored = EvidenceLedger()
    errored.record("a", ERROR)
    assert errored.arc_status()[0] == "blocked"


def test_arc_status_watchlists_a_soft_gap():
    led = EvidenceLedger()
    led.expect("a")  # expected but never run -> MISSING (a soft gap, not a hard fail)
    led.record("b", PASSED)
    assert led.arc_status()[0] == "watchlist"
