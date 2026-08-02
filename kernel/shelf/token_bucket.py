"""CARD: token_bucket -- rate limiting by the token-bucket algorithm: a sustained rate with bursts.

A bucket holds up to `capacity` tokens and refills at `rate` tokens per second. An action costs
tokens; it is allowed only if the bucket holds enough, which caps the sustained rate while letting
short bursts through (up to the capacity). This is the standard token-bucket limiter, reimplemented
from the algorithm (not copied): study the concept, build the behavior.

Framework-free and deterministic: the clock is INJECTED (default `time.monotonic`), so tests pin
exact behavior without sleeping and property tests can drive any timeline. It never renders, never
mutates world state, and holds no I/O. One core, two lives: it throttles a player's shouts in the
game (`parts/chat_throttle`) and login attempts in a practical app (`parts/login_guard`).

Provenance: independently_implemented_pattern (token-bucket algorithm, public-domain CS; see
docs/hardware/token-bucket.yaml). No code copied.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

Clock = Callable[[], float]  # monotonic seconds


class RateLimitError(ValueError):
    """A token bucket was built with an invalid rate, capacity, or cost. Fails loud at the gate."""


@dataclass(frozen=True)
class ThrottleDecision:
    """The verdict for one throttled action: allowed or not, with the wait until it would be."""

    allowed: bool
    tokens_left: float
    retry_after: float  # seconds until `cost` tokens are available (0.0 when allowed)
    reason: str = ""


def _require_positive(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise RateLimitError(f"{name} must be a finite number, got {value!r}")
    if value <= 0:
        raise RateLimitError(f"{name} must be positive, got {value}")
    return float(value)


@dataclass
class TokenBucket:
    """A refilling token bucket. Not thread-safe by design (the engine tick is single-threaded);
    a concurrent variant is a later, deliberate juncture."""

    rate: float  # tokens added per second
    capacity: float  # maximum tokens held (the burst size)
    clock: Clock | None = None  # injected; defaults to time.monotonic at construction
    _tokens: float = field(init=False, default=0.0)
    _last: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.rate = _require_positive("rate", self.rate)
        self.capacity = _require_positive("capacity", self.capacity)
        self._clock: Clock = self.clock or time.monotonic
        self._tokens = self.capacity  # a fresh bucket starts full
        self._last = self._clock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)  # a non-monotonic clock never removes tokens
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    def _validate_cost(self, cost: float) -> float:
        cost = (
            float(cost)
            if isinstance(cost, (int, float)) and not isinstance(cost, bool)
            else math.nan
        )
        if not math.isfinite(cost) or cost < 0:
            raise RateLimitError(f"cost must be a finite, non-negative number, got {cost!r}")
        if cost > self.capacity:
            raise RateLimitError(
                f"cost {cost} exceeds capacity {self.capacity}; it could never fit"
            )
        return cost

    def check(self, cost: float = 1.0) -> ThrottleDecision:
        """Peek: would `cost` be allowed now? Refills but never consumes."""
        cost = self._validate_cost(cost)
        self._refill()
        if self._tokens >= cost:
            return ThrottleDecision(True, self._tokens, 0.0)
        deficit = cost - self._tokens
        return ThrottleDecision(False, self._tokens, deficit / self.rate, "rate limit exceeded")

    def consume(self, cost: float = 1.0) -> ThrottleDecision:
        """Take `cost` tokens if available; otherwise deny with the wait until it would be."""
        decision = self.check(cost)
        if decision.allowed:
            self._tokens -= cost
            return ThrottleDecision(True, self._tokens, 0.0)
        return decision
