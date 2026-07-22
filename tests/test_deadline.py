"""Test twin for parts/deadline.py -- a pollable time budget with an injected clock.

Deterministic: a fake clock drives every span, so no test waits on real time. Acceptance
(budget counts down, expires, resets) AND refusal (a negative / NaN / bool / infinite budget
fails loud at construction).
"""

from __future__ import annotations

import math

import pytest

from parts.shelf.deadline import Deadline, DeadlineError, DeadlineExceeded


class FakeClock:
    """A hand-cranked monotonic clock: `advance(dt)` moves time forward for the test."""

    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


# --- acceptance -----------------------------------------------------------------------
def test_a_fresh_deadline_has_the_full_budget_remaining() -> None:
    clock = FakeClock()
    d = Deadline(5.0, clock=clock)
    assert d.remaining() == 5.0
    assert d.elapsed() == 0.0
    assert not d.expired()


def test_the_budget_counts_down_as_the_clock_advances() -> None:
    clock = FakeClock()
    d = Deadline(5.0, clock=clock)
    clock.advance(2.0)
    assert d.elapsed() == 2.0
    assert d.remaining() == 3.0
    assert not d.expired()


def test_the_deadline_expires_when_the_budget_is_spent() -> None:
    clock = FakeClock()
    d = Deadline(5.0, clock=clock)
    clock.advance(5.0)
    assert d.expired() and d.remaining() == 0.0
    clock.advance(10.0)  # well past the budget
    assert d.expired() and d.remaining() == 0.0  # clamps at zero, never negative


def test_a_zero_budget_is_expired_immediately() -> None:
    d = Deadline(0.0, clock=FakeClock())
    assert d.expired() and d.remaining() == 0.0


def test_check_raises_only_once_the_budget_is_spent() -> None:
    clock = FakeClock()
    d = Deadline(3.0, clock=clock)
    d.check()  # still time left -> no raise
    clock.advance(3.0)
    with pytest.raises(DeadlineExceeded, match="exceeded"):
        d.check()


def test_reset_starts_the_budget_over() -> None:
    clock = FakeClock()
    d = Deadline(4.0, clock=clock)
    clock.advance(4.0)
    assert d.expired()
    d.reset()
    assert not d.expired() and d.remaining() == 4.0


def test_a_backwards_clock_never_yields_negative_elapsed() -> None:
    clock = FakeClock(start=100.0)
    d = Deadline(5.0, clock=clock)
    clock.now = 90.0  # a stray step backwards (should not happen with monotonic, but stay safe)
    assert d.elapsed() == 0.0  # clamped, not -10
    assert d.remaining() == 5.0


# --- refusal (fail loud at construction) ----------------------------------------------
def test_a_negative_budget_is_refused() -> None:
    with pytest.raises(DeadlineError, match="non-negative"):
        Deadline(-1.0)


def test_a_non_finite_budget_is_refused() -> None:
    for bad in (math.inf, -math.inf, math.nan):
        with pytest.raises(DeadlineError, match="finite"):
            Deadline(bad)


def test_a_bool_budget_is_refused_not_treated_as_one_second() -> None:
    # True is an int in Python; a Deadline of "True seconds" is a bug, so refuse it loud.
    with pytest.raises(DeadlineError, match="finite"):
        Deadline(
            True
        )  # a bool is an int at runtime; the guard refuses it (mypy allows bool as float)


def test_a_non_numeric_budget_is_refused() -> None:
    with pytest.raises(DeadlineError, match="finite"):
        Deadline("5")  # type: ignore[arg-type]
