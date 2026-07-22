"""CARD: retry -- retry with exponential backoff: transient failures recover, permanent ones don't.

A `RetryPolicy` decides how many times to try, which exceptions count as transient, and how long to
wait between tries (exponential backoff, capped). `run_with_retries` runs a callable under a policy:
it retries a transient failure, re-raises a permanent one immediately, and after the last attempt
re-raises the final failure (never swallowed). This is the standard retry/backoff pattern,
reimplemented from the concept (AWS Prescriptive Guidance, "retry with backoff") -- no code copied.

Framework-free and deterministic: the SLEEP is injected (default `time.sleep`), so tests pin the
exact backoff schedule and attempt count without waiting. It holds no I/O of its own. One core, two
lives: it auto-retries a flaky calibration in the game (`parts/calibrate`) and an unreliable API/DB
call in a practical app (`parts/resilient_call`).

Composes with the Hardware Store's `deadline` part: pass an optional `Deadline` to bound the TOTAL
wall-clock time of the retry loop, so a flaky call retries within a time budget, not just an attempt
count. When the budget is spent, retrying stops early and the last transient failure is re-raised.

Provenance: independently_implemented_pattern (retry/exponential-backoff; see
docs/hardware/retry-policy.yaml). No code copied.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from parts.deadline import Deadline

Sleep = Callable[[float], None]
OnRetry = Callable[["Attempt"], None]

# Default source of backoff jitter. Not security-sensitive (it spreads retries in time to avoid a
# thundering herd), so a plain Random is right; callers inject a seeded one for deterministic tests.
_JITTER_RNG = random.Random()  # nosec B311 -- backoff jitter, not a security decision


class RetryError(ValueError):
    """A retry policy was built with invalid settings. Fails loud at construction."""


@dataclass(frozen=True)
class Attempt:
    """One recorded try that failed transiently and will be retried after `delay` seconds."""

    number: int  # 1-indexed attempt that just failed
    delay: float  # seconds waited before the next attempt
    error: str  # repr of the transient exception


def _finite_nonneg(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise RetryError(f"{name} must be a finite number, got {value!r}")
    if value < 0:
        raise RetryError(f"{name} must be non-negative, got {value}")
    return float(value)


@dataclass(frozen=True)
class RetryPolicy:
    """How to retry: attempt budget, which exceptions are transient, and the backoff schedule."""

    max_attempts: int
    base_delay: float = 0.1
    factor: float = 2.0
    max_delay: float = 30.0
    retry_on: tuple[type[Exception], ...] = (Exception,)
    jitter: bool = False  # full jitter: sleep a random span in [0, the capped backoff] each try

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise RetryError(f"max_attempts must be an int, got {self.max_attempts!r}")
        if self.max_attempts < 1:
            raise RetryError(f"max_attempts must be >= 1, got {self.max_attempts}")
        _finite_nonneg("base_delay", self.base_delay)
        _finite_nonneg("max_delay", self.max_delay)
        if not math.isfinite(self.factor) or self.factor < 1:
            raise RetryError(f"factor must be >= 1, got {self.factor}")
        if not self.retry_on:
            raise RetryError("retry_on must name at least one exception type")

    def is_transient(self, exc: BaseException) -> bool:
        """True if `exc` is one the policy will retry."""
        return isinstance(exc, self.retry_on)

    def delay_for(self, attempt: int) -> float:
        """Seconds to wait after the 1-indexed `attempt`: base * factor**(attempt-1), capped."""
        raw = self.base_delay * (self.factor ** (attempt - 1))
        return min(self.max_delay, raw)


def run_with_retries[T](
    fn: Callable[[], T],
    policy: RetryPolicy,
    *,
    sleep: Sleep = time.sleep,
    on_retry: OnRetry | None = None,
    deadline: Deadline | None = None,
    rng: random.Random | None = None,
) -> T:
    """Run `fn` under `policy`. Retry transient failures; re-raise permanent and final ones.

    An optional `deadline` caps the TOTAL wall-clock time: once its budget is spent, retrying stops
    early (no further attempt) and the last transient failure is re-raised, unswallowed. When the
    policy sets `jitter`, each backoff is a random span in [0, the capped delay] (full jitter, to
    spread a fleet's retries and avoid a thundering herd); inject `rng` for a deterministic test."""
    last: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # KeyboardInterrupt/SystemExit are BaseException and propagate
            if not policy.is_transient(exc):
                raise  # permanent: do not retry, do not swallow
            last = exc
            if deadline is not None and deadline.expired():
                break  # time budget spent: stop retrying, re-raise the last failure below
            if attempt < policy.max_attempts:
                delay = policy.delay_for(attempt)
                if policy.jitter:
                    delay = (rng or _JITTER_RNG).uniform(0.0, delay)  # full jitter in [0, ceiling]
                if on_retry is not None:
                    on_retry(Attempt(attempt, delay, repr(exc)))
                sleep(delay)
    assert last is not None  # max_attempts >= 1, so the loop body ran and set last
    raise last  # attempts exhausted (or budget spent): re-raise the last transient failure
