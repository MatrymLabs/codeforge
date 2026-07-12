"""CARD: relay -- the game adapter for the circuit breaker: a flaky power relay that can trip.

A player `channel`s power through a temperamental relay. Each draw may surge and fail; too many
consecutive failures trip the breaker and the relay refuses further draws until it cools (fail
fast), then lets one probe through. The SAME `CircuitBreaker` core protects an unreliable upstream
service in a practical app (parts/service_breaker); only the adapter differs.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from parts.circuit_breaker import CircuitBreaker, CircuitOpen, Clock
from parts.session import Session

_THRESHOLD = 3
_RESET = 30.0
_BREAKER = CircuitBreaker(failure_threshold=_THRESHOLD, reset_timeout=_RESET)
_rng_override: Callable[[], float] | None = None


class _RelayFault(Exception):
    """The relay surged and failed this draw (a transient failure the breaker counts)."""


def _draw_once(rng: Callable[[], float]) -> str:
    if rng() < 0.7:  # surges more often than not
        raise _RelayFault("surge")
    return "power flows"


def channel(session: Session, arg: str = "") -> str:
    """The `channel` verb: draw power through the relay, protected by a circuit breaker."""
    rng = _rng_override or random.random
    try:
        _BREAKER.call(lambda: _draw_once(rng))
        return "You channel power through the relay. Power flows."
    except CircuitOpen:
        return "The relay has tripped shut. Wait for it to cool before channeling again."
    except _RelayFault:
        return f"The relay sparks and fails. (relay: {_BREAKER.state()})"


def reset_relay(clock: Clock | None = None, rng: Callable[[], float] | None = None) -> None:
    """Test hook: rebuild the relay's breaker with an injected clock and inject its rng."""
    global _BREAKER, _rng_override
    _BREAKER = CircuitBreaker(failure_threshold=_THRESHOLD, reset_timeout=_RESET, clock=clock)
    _rng_override = rng
