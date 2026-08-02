"""CARD: deadline -- a pollable time budget: a fixed span, after which work should stop.

The single-threaded cousin of a timeout. A hard timeout interrupts a thread; a `Deadline` does not
interrupt anything -- it is an honest "time's up" you POLL between steps (each tick, retry, or batch
item), so a long job yields the moment its budget is spent instead of running unbounded. This is the
standard deadline/time-budget pattern (gRPC / context deadlines), reimplemented from the concept --
no code copied.

Framework-free and deterministic: the CLOCK is injected (default `time.monotonic`), so tests pin the
budget exactly without waiting. It holds no I/O of its own. One core, two lives: it caps the TOTAL
wall-clock time of a retry loop in a practical app (`run_with_retries(..., deadline=...)`, so a
flaky call retries within a budget, not just an attempt count), and it bounds any long-running span
whose caller must stay responsive (a real-time timed challenge, a batch that must finish in an SLA).

Provenance: independently_implemented_pattern (deadline / time budget). No code copied.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

Clock = Callable[[], float]


class DeadlineError(ValueError):
    """A deadline was built with an invalid budget. Fails loud at construction."""


class DeadlineExceeded(Exception):
    """The budget is spent. Raised by `check()` so a caller can stop loud, not poll-and-branch."""


@dataclass
class Deadline:
    """A budget of `seconds` from a start instant (the moment it is created). Poll `remaining()` /
    `expired()` between steps, or `check()` to stop loud; `reset()` restarts it. The clock is
    INJECTED (default `time.monotonic`) and assumed monotonic, so time never goes back."""

    seconds: float
    clock: Clock | None = None
    _clock: Clock = field(init=False)
    _start: float = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.seconds, (int, float))
            or isinstance(self.seconds, bool)
            or not math.isfinite(self.seconds)
        ):
            raise DeadlineError(f"seconds must be a finite number, got {self.seconds!r}")
        if self.seconds < 0:
            raise DeadlineError(f"seconds must be non-negative, got {self.seconds}")
        self._clock = self.clock or time.monotonic
        self._start = self._clock()

    def elapsed(self) -> float:
        """Seconds since the budget started (never negative, even if a stray clock ticks back)."""
        return max(0.0, self._clock() - self._start)

    def remaining(self) -> float:
        """Seconds left in the budget, clamped at zero (never negative)."""
        return max(0.0, self.seconds - self.elapsed())

    def expired(self) -> bool:
        """True once the budget is spent (a zero budget is expired immediately)."""
        return self.remaining() <= 0.0

    def check(self) -> None:
        """Raise DeadlineExceeded if the budget is spent; otherwise return. Fail-loud polling."""
        if self.expired():
            raise DeadlineExceeded(
                f"deadline of {self.seconds}s exceeded ({self.elapsed():.3f}s elapsed)"
            )

    def reset(self) -> None:
        """Start the budget over from now (reuse one Deadline across repeated spans)."""
        self._start = self._clock()
