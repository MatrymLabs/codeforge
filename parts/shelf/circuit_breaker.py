"""CARD: circuit_breaker -- fail fast when a service is broken; test recovery after a timeout.

A circuit breaker guards calls to a flaky dependency. CLOSED, it passes calls and counts consecutive
failures; at a threshold it trips to OPEN and rejects calls immediately (no waiting on a dead
service). After a reset timeout it moves to HALF_OPEN and lets ONE probe through: success closes it,
failure opens it again. This is the standard circuit-breaker pattern (Azure resilience),
reimplemented from the concept -- no code copied.

Composition, not reinvention: the three-state lifecycle IS a state machine, so the breaker is built
ON the Hardware Store's own `state-machine` part (`parts/statemachine`); the breaker adds only the
failure counting and the timing that decide which transition fires. Framework-free and
deterministic: the clock is INJECTED (default `time.monotonic`). One core, two lives: it protects a
flaky relay in the game (`parts/relay`) and an unreliable upstream service in a practical app
(`parts/service_breaker`).

Provenance: independently_implemented_pattern (circuit breaker). No code copied.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from parts.shelf.statemachine import Fired, Transition, advance, build

Clock = Callable[[], float]

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

# The lifecycle graph, as a validated Machine (composition on the state-machine part).
_MACHINE = build(
    states=[CLOSED, OPEN, HALF_OPEN],
    start=CLOSED,
    transitions=[
        Transition(CLOSED, "trip", OPEN),  # too many consecutive failures
        Transition(OPEN, "timeout", HALF_OPEN),  # reset window elapsed; probe recovery
        Transition(HALF_OPEN, "success", CLOSED),  # the probe worked
        Transition(HALF_OPEN, "failure", OPEN),  # the probe failed; re-open
    ],
)


class CircuitBreakerError(ValueError):
    """A circuit breaker was built with invalid settings. Fails loud at construction."""


class CircuitOpen(Exception):
    """A call was rejected because the breaker is open (fail fast, do not run the operation)."""


@dataclass
class CircuitBreaker:
    """Trip to OPEN after `failure_threshold` consecutive failures; probe again after
    `reset_timeout` seconds. Not thread-safe by design (the engine tick is single-threaded)."""

    failure_threshold: int
    reset_timeout: float
    clock: Clock | None = None
    _state: str = field(init=False, default=CLOSED)
    _failures: int = field(init=False, default=0)
    _opened_at: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if not isinstance(self.failure_threshold, int) or isinstance(self.failure_threshold, bool):
            raise CircuitBreakerError(
                f"failure_threshold must be an int, got {self.failure_threshold!r}"
            )
        if self.failure_threshold < 1:
            raise CircuitBreakerError(
                f"failure_threshold must be >= 1, got {self.failure_threshold}"
            )
        if not math.isfinite(self.reset_timeout) or self.reset_timeout < 0:
            raise CircuitBreakerError("reset_timeout must be a finite, non-negative number")
        self._clock: Clock = self.clock or time.monotonic
        self._state = _MACHINE.start

    def _fire(self, event: str) -> None:
        outcome = advance(_MACHINE, self._state, event)
        if isinstance(outcome, Fired):  # an illegal event for the current state is ignored
            self._state = outcome.dst

    def _maybe_recover(self) -> None:
        if self._state == OPEN and (self._clock() - self._opened_at) >= self.reset_timeout:
            self._fire("timeout")  # OPEN -> HALF_OPEN

    def state(self) -> str:
        """The current state, accounting for a reset timeout that may have elapsed."""
        self._maybe_recover()
        return self._state

    def allow(self) -> bool:
        """Whether a call may proceed now (open rejects; closed and half-open allow)."""
        return self.state() != OPEN

    def record_success(self) -> None:
        if self._state == HALF_OPEN:
            self._fire("success")  # HALF_OPEN -> CLOSED
        self._failures = 0

    def record_failure(self) -> None:
        self._maybe_recover()
        if self._state == HALF_OPEN:
            self._fire("failure")  # HALF_OPEN -> OPEN
            self._opened_at = self._clock()
        elif self._state == CLOSED:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._fire("trip")  # CLOSED -> OPEN
                self._opened_at = self._clock()

    def call[T](self, fn: Callable[[], T]) -> T:
        """Run `fn` if the breaker allows; else raise CircuitOpen. Records the outcome."""
        if not self.allow():
            raise CircuitOpen("circuit is open; call rejected")
        try:
            result = fn()
        except Exception:
            self.record_failure()  # the failure is recorded, then re-raised (never swallowed)
            raise
        self.record_success()
        return result
