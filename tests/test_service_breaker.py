"""Test twin for parts/service_breaker.py -- the practical adapter + the one-core proof."""

import pytest

from parts.service_breaker import ServiceBreakers
from parts.shelf.circuit_breaker import OPEN, CircuitBreaker, CircuitOpen


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class Down(Exception):
    pass


def _fail():
    raise Down("upstream down")


def test_a_broken_service_trips_independently_of_a_healthy_one():
    sb = ServiceBreakers(failure_threshold=2, reset_timeout=10, clock=FakeClock())
    for _ in range(2):
        with pytest.raises(Down):
            sb.call("payments", _fail)
    assert sb.state("payments") == OPEN
    assert sb.call("search", lambda: "ok") == "ok"  # a different service is unaffected


def test_an_open_service_rejects_fast():
    sb = ServiceBreakers(failure_threshold=1, reset_timeout=10, clock=FakeClock())
    with pytest.raises(Down):
        sb.call("api", _fail)  # trips it
    with pytest.raises(CircuitOpen):
        sb.call("api", lambda: "ok")


def test_it_recovers_after_the_reset_timeout():
    clk = FakeClock()
    sb = ServiceBreakers(failure_threshold=1, reset_timeout=10, clock=clk)
    with pytest.raises(Down):
        sb.call("api", _fail)
    clk.advance(10)
    assert sb.call("api", lambda: "ok") == "ok"  # half-open probe succeeds -> closed


def test_one_core_powers_both_the_game_relay_and_the_practical_service_breaker():
    import parts.relay as game

    sb = ServiceBreakers(clock=FakeClock())
    sb.call("x", lambda: "ok")
    assert all(isinstance(b, CircuitBreaker) for b in sb._breakers.values())
    assert isinstance(game._BREAKER, CircuitBreaker)  # the game relay is the same core
