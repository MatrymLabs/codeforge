"""Test twin for parts/circuit_breaker.py -- fail-fast and recovery via a fake clock."""

import contextlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.circuit_breaker import (
    CLOSED,
    HALF_OPEN,
    OPEN,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitOpen,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class Boom(Exception):
    pass


def _fail():
    raise Boom("down")


@pytest.mark.parametrize(
    "kwargs",
    [{"failure_threshold": 0, "reset_timeout": 10}, {"failure_threshold": 1, "reset_timeout": -1}],
)
def test_a_bad_config_fails_loud(kwargs):
    with pytest.raises(CircuitBreakerError):
        CircuitBreaker(**kwargs)


def test_it_starts_closed_and_passes_calls():
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=10, clock=FakeClock())
    assert cb.state() == CLOSED
    assert cb.call(lambda: "ok") == "ok"


def test_it_trips_open_after_the_failure_threshold():
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=10, clock=FakeClock())
    for _ in range(3):
        with pytest.raises(Boom):
            cb.call(_fail)
    assert cb.state() == OPEN


def test_an_open_circuit_rejects_fast_without_running_the_call():
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10, clock=FakeClock())
    with pytest.raises(Boom):
        cb.call(_fail)  # trips it
    ran = {"called": False}

    def op():
        ran["called"] = True
        return "ok"

    with pytest.raises(CircuitOpen):
        cb.call(op)
    assert ran["called"] is False  # fail fast: the operation never ran


def test_after_the_timeout_it_half_opens_and_a_probe_success_closes_it():
    clk = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10, clock=clk)
    with pytest.raises(Boom):
        cb.call(_fail)  # open
    clk.advance(10)  # reset window elapses
    assert cb.state() == HALF_OPEN
    assert cb.call(lambda: "ok") == "ok"  # the probe succeeds
    assert cb.state() == CLOSED


def test_a_probe_failure_reopens_the_circuit():
    clk = FakeClock()
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=10, clock=clk)
    with pytest.raises(Boom):
        cb.call(_fail)  # open
    clk.advance(10)
    assert cb.state() == HALF_OPEN
    with pytest.raises(Boom):
        cb.call(_fail)  # probe fails
    assert cb.state() == OPEN


def test_a_success_resets_the_consecutive_failure_count():
    cb = CircuitBreaker(failure_threshold=3, reset_timeout=10, clock=FakeClock())
    with pytest.raises(Boom):
        cb.call(_fail)
    with pytest.raises(Boom):
        cb.call(_fail)
    cb.call(lambda: "ok")  # resets the streak
    with pytest.raises(Boom):
        cb.call(_fail)
    assert cb.state() == CLOSED  # only one failure since the reset; not tripped


@pytest.mark.property
@given(
    threshold=st.integers(min_value=1, max_value=10),
    outcomes=st.lists(st.booleans(), max_size=40),  # True = success, False = failure
)
def test_it_opens_exactly_when_a_run_of_threshold_failures_occurs(threshold, outcomes):
    # Time frozen: the breaker opens iff there is a run of >= threshold consecutive failures.
    cb = CircuitBreaker(failure_threshold=threshold, reset_timeout=1e9, clock=FakeClock())
    run = 0
    expected_open = False
    for ok in outcomes:
        if cb.state() == OPEN:
            expected_open = True
            break  # once open with frozen time, it stays open; stop feeding it
        run = 0 if ok else run + 1
        with contextlib.suppress(Boom):
            cb.call((lambda: "ok") if ok else _fail)
        if run >= threshold:
            expected_open = True
    assert (cb.state() == OPEN) == expected_open
