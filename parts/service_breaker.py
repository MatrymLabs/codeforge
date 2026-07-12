"""CARD: service_breaker -- the practical adapter for the circuit breaker: per-service breakers.

The reverse of parts/relay: the SAME `CircuitBreaker` core, driven by a plain (non-game) registry
that keeps ONE breaker per named upstream service, so a broken payment gateway trips independently
of a slow search service. Its cousins protect any API/DB/RPC dependency from cascading failures.
The clock is injected so callers (and tests) control the reset timing.
"""

from __future__ import annotations

from collections.abc import Callable

from parts.circuit_breaker import CircuitBreaker, Clock


class ServiceBreakers:
    """A registry of circuit breakers, one per named service, created on first use."""

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        clock: Clock | None = None,
    ) -> None:
        self._threshold = failure_threshold
        self._timeout = reset_timeout
        self._clock = clock
        self._breakers: dict[str, CircuitBreaker] = {}

    def _breaker(self, name: str) -> CircuitBreaker:
        breaker = self._breakers.get(name)
        if breaker is None:
            breaker = self._breakers[name] = CircuitBreaker(
                self._threshold, self._timeout, clock=self._clock
            )
        return breaker

    def call[T](self, name: str, fn: Callable[[], T]) -> T:
        """Run `fn` for service `name` under its own breaker; raises CircuitOpen if it is open."""
        return self._breaker(name).call(fn)

    def state(self, name: str) -> str:
        """The current breaker state for one service."""
        return self._breaker(name).state()
