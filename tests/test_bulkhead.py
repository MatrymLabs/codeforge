"""Test twin for parts/bulkhead.py -- bounded-concurrency isolation.

Acceptance (a slot admits, releases, and is freed even on error) AND refusal (a limit < 1 or a
bool/non-int fails loud). The concurrency test is DETERMINISTIC: threads hold their slots on an
Event until the test releases them, and readiness is polled with a deadline, never asserted on an
instant (a raced instant-assert is the classic flaky-test trap).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest

from parts.shelf.bulkhead import Bulkhead, BulkheadError, BulkheadFull


def _wait_until(pred: Callable[[], bool], timeout: float = 2.0) -> bool:
    """Poll `pred` until true or the deadline passes (no instant assertion on a threaded state)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.005)
    return pred()


# --- acceptance -----------------------------------------------------------------------
def test_run_admits_and_returns_within_the_limit() -> None:
    bh = Bulkhead(2)
    assert bh.run(lambda: "ok") == "ok"
    assert bh.active == 0 and bh.available == 2  # slot released after the call


def test_a_raising_operation_still_releases_its_slot() -> None:
    bh = Bulkhead(1)

    def boom() -> None:
        raise ValueError("work failed")

    with pytest.raises(ValueError, match="work failed"):
        bh.run(boom)
    assert bh.active == 0 and bh.available == 1  # the compartment never leaks capacity


def test_sequential_runs_reuse_the_same_slot() -> None:
    bh = Bulkhead(1)
    for _ in range(5):
        assert bh.run(lambda: 1) == 1
    assert bh.available == 1


def test_the_slot_context_manager_tracks_active_count() -> None:
    bh = Bulkhead(2)
    with bh.slot():
        assert bh.active == 1 and bh.available == 1
        with bh.slot():
            assert bh.active == 2 and bh.available == 0
    assert bh.active == 0


# --- refusal (fail loud at construction) ----------------------------------------------
def test_a_zero_limit_is_refused() -> None:
    with pytest.raises(BulkheadError, match=">= 1"):
        Bulkhead(0)


def test_a_negative_limit_is_refused() -> None:
    with pytest.raises(BulkheadError, match=">= 1"):
        Bulkhead(-3)


def test_a_bool_limit_is_refused_not_treated_as_one() -> None:
    with pytest.raises(BulkheadError, match="int"):
        Bulkhead(True)  # a bool is an int at runtime; a bulkhead of "True" is a bug


def test_a_non_int_limit_is_refused() -> None:
    with pytest.raises(BulkheadError, match="int"):
        Bulkhead(2.5)  # type: ignore[arg-type]


# --- concurrency (deterministic: threads hold slots on an Event) ----------------------
def test_the_cap_holds_under_contention_and_rejects_the_overflow() -> None:
    bh = Bulkhead(2)
    release = threading.Event()
    errors: list[BaseException] = []

    def hold() -> None:
        def block() -> None:
            release.wait(timeout=5.0)  # keep the slot until the test releases it

        try:
            bh.run(block)
        except BaseException as exc:  # noqa: BLE001 -- record, so a thread failure surfaces
            errors.append(exc)

    workers = [threading.Thread(target=hold) for _ in range(2)]
    for w in workers:
        w.start()

    # Both slots must fill; poll rather than assume an instant.
    assert _wait_until(lambda: bh.active == 2), f"expected 2 active, saw {bh.active}"
    assert bh.available == 0

    # A third entrant, while the compartment is full, is rejected fast.
    with pytest.raises(BulkheadFull, match="full"):
        bh.run(lambda: "overflow")

    release.set()
    for w in workers:
        w.join(timeout=5.0)
    assert not errors  # the two admitted workers ran cleanly
    assert _wait_until(lambda: bh.active == 0) and bh.available == 2  # capacity restored
