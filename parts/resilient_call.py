"""CARD: resilient_call -- the practical adapter for retry: an unreliable call with an audit trail.

The reverse of parts/calibrate: the SAME `run_with_retries` core, driven by a plain (non-game)
object that wraps a retry policy and keeps a HISTORY of the attempts it made -- the audit trail that
practical resilience needs (failures recorded, never swallowed). Its cousins are retrying a flaky
HTTP API, a database call, or any transient-fault-prone integration. The sleep is injected, so
callers control (and tests pin) the backoff.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from parts.retry import Attempt, RetryPolicy, Sleep, run_with_retries


class ResilientCaller:
    """Run an unreliable callable under a retry policy, recording each retried attempt."""

    def __init__(self, policy: RetryPolicy, *, sleep: Sleep | None = None) -> None:
        self.policy = policy
        self._sleep: Sleep = sleep or time.sleep
        self.history: list[Attempt] = []

    def call[T](self, fn: Callable[[], T]) -> T:
        """Run `fn` with retries; the attempt history is available on `self.history` afterward."""
        self.history = []
        return run_with_retries(fn, self.policy, sleep=self._sleep, on_retry=self.history.append)
