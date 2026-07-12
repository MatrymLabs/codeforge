"""CARD: login_guard -- the practical adapter for the token bucket: rate-limit login attempts.

The reverse of parts/chat_throttle: the SAME `TokenBucket` core, driven by a plain (non-game)
function, guarding an account or IP against brute-force login attempts (a burst of 5, refilling one
every 30 seconds). It returns an allow/deny DECISION with a `retry_after`; it does NOT authenticate
(password hashing stays in parts/accounts on stdlib pbkdf2) -- this is only the throttle policy. Its
practical cousins are API quotas, email-send caps, and any "N per window" governor.
"""

from __future__ import annotations

from parts.token_bucket import Clock, ThrottleDecision, TokenBucket

_ATTEMPTS = 5.0  # burst of five attempts
_REFILL = 1 / 30  # one attempt refills every 30 seconds


class LoginGuard:
    """A per-key login-attempt limiter. One bucket per key (account or IP), made on first use."""

    def __init__(
        self,
        attempts: float = _ATTEMPTS,
        refill_per_sec: float = _REFILL,
        clock: Clock | None = None,
    ) -> None:
        self._attempts = attempts
        self._refill = refill_per_sec
        self._clock = clock
        self._buckets: dict[str, TokenBucket] = {}

    def attempt(self, key: str) -> ThrottleDecision:
        """Record one login attempt for `key`; allow it or refuse with the wait until the next."""
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._buckets[key] = TokenBucket(
                self._refill, self._attempts, clock=self._clock
            )
        return bucket.consume()
