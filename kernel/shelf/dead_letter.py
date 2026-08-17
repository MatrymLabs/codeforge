"""CARD: dead_letter -- a dead-letter queue: hold the messages that could not be processed, safely.

The last part in the at-least-once family. `retry` makes a failed call happen again; `idempotency`
makes that repeat safe; but some messages fail *permanently* (a poison message, a bad payload, a
downstream that stays down). Dropping them loses data; retrying them forever blocks the queue. A
dead-letter queue is the third answer: set the exhausted message aside, with the reason it failed
and how many times it was tried, so an operator can inspect it and later replay it once the cause is
fixed. This is the documented messaging pattern (RabbitMQ dead-letter exchanges, SQS dead-letter
queues, Kafka dead-letter topics), reconstructed as a small in-process core.

What it does:

- **bury** a message that exhausted its retries, with a reason and an attempt count.
- **stay bounded.** A DLQ that grows without limit is a memory leak; this one has a capacity and,
  when full, drops the OLDEST letter and counts the drop (never silently -- `dropped` is queryable
  and is exactly what you alert on). Keeping the most recent failures is usually the right triage.
- **inspect** the buried letters (an immutable snapshot), and **replay** them through a handler:
  a letter the handler now accepts is recovered and leaves the queue; one that still fails stays,
  with its reason and attempt count updated (the "redrive" operation).

Fail-loud: a zero capacity, an empty reason, or a negative attempt count is refused. It stores and
replays; it does not itself retry (compose it with `retry`). In-memory and single-process; a
networked deployment maps this onto a broker's real dead-letter queue.

Provenance: original implementation of the publicly documented dead-letter-queue pattern. No code
copied; not affiliated with any broker.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


class DeadLetterError(ValueError):
    """A refused dead-letter operation (bad capacity, empty reason, or bad attempts): fail loud."""


@dataclass(frozen=True)
class DeadLetter[T]:
    """One buried message: the payload, why it failed, and how many times it was tried."""

    message: T
    reason: str
    attempts: int


@dataclass(frozen=True)
class ReplayResult[T]:
    """The outcome of a replay pass: which letters recovered and which are still dead."""

    recovered: tuple[T, ...]
    still_dead: tuple[DeadLetter[T], ...]


@dataclass
class DeadLetterQueue[T]:
    """A bounded store of messages that could not be processed, for inspection and replay.

    In-memory and single-process. A networked deployment maps this onto a broker's dead-letter
    queue (RabbitMQ/SQS/Kafka); the contract -- bury with a reason, inspect, replay/redrive -- is
    the same.
    """

    capacity: int = 128
    _letters: list[DeadLetter[T]] = field(default_factory=list)
    _dropped: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.capacity, int) or isinstance(self.capacity, bool):
            raise DeadLetterError(f"capacity must be an int, got {self.capacity!r}")  # noqa: TRY003
        if self.capacity < 1:
            raise DeadLetterError(f"capacity must be >= 1, got {self.capacity}")  # noqa: TRY003

    def bury(self, message: T, reason: str, *, attempts: int = 1) -> DeadLetter[T]:
        """Set aside a message that could not be processed, with the reason and attempt count.

        Fails loud on an empty reason or a negative attempt count. When the queue is at capacity,
        the OLDEST letter is dropped and `dropped` is incremented (never silently); the new letter
        is always kept, so the most recent failure is never lost to make room.
        """
        if not reason or not reason.strip():
            raise DeadLetterError("a dead letter needs a non-empty reason")  # noqa: TRY003
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
            raise DeadLetterError(f"attempts must be a non-negative int, got {attempts!r}")  # noqa: TRY003
        letter = DeadLetter(message=message, reason=reason, attempts=attempts)
        self._letters.append(letter)
        while len(self._letters) > self.capacity:
            self._letters.pop(0)  # drop the oldest to stay bounded...
            self._dropped += 1  # ...but count it, so overflow is visible and alertable
        return letter

    def letters(self) -> tuple[DeadLetter[T], ...]:
        """The buried letters, oldest first (an immutable snapshot)."""
        return tuple(self._letters)

    @property
    def dropped(self) -> int:
        """How many letters were dropped to stay within capacity (alert if this is ever > 0)."""
        return self._dropped

    def is_empty(self) -> bool:
        """Whether the queue currently holds no letters."""
        return not self._letters

    def __len__(self) -> int:
        return len(self._letters)

    def replay(self, handler: Callable[[T], object]) -> ReplayResult[T]:
        """Re-run `handler` over every buried message (the redrive operation).

        A message the handler now accepts (returns without raising) is recovered and removed from
        the queue. One that still raises stays buried, its reason replaced by the new failure and
        its attempt count incremented. Returns the recovered payloads and the letters still dead.
        Order is preserved; `dropped` is not affected (replay never drops).
        """
        recovered: list[T] = []
        still_dead: list[DeadLetter[T]] = []
        for letter in self._letters:
            try:
                handler(letter.message)
            except Exception as exc:  # noqa: BLE001 - replay records the failure, never propagates it
                still_dead.append(
                    DeadLetter(
                        message=letter.message,
                        reason=str(exc) or exc.__class__.__name__,
                        attempts=letter.attempts + 1,
                    )
                )
            else:
                recovered.append(letter.message)
        self._letters = still_dead
        return ReplayResult(recovered=tuple(recovered), still_dead=tuple(still_dead))
