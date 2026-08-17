"""CARD: jobqueue -- a durable work queue with a visibility lease, retries, and dead-lettering.

Clean-room reconstruction of the competing-consumers work-queue pattern with a
visibility timeout (SQS-style) and fencing tokens (Kleppmann). Standard library
only.

A worker claims the next available job under a lease; if it crashes mid-job the
lease elapses and reclaim_expired() redelivers the job to another worker. A
monotonic fencing token invalidates a stale worker's ack, so a reclaimed job is
completed by exactly one live worker. Poison jobs dead-letter at a max-attempts
bound. Delivery is at-least-once; consumers must be idempotent.

This is the reference mechanism with an in-memory store; production backs jobs in
a table with a deadline index.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

AVAILABLE = "available"
CLAIMED = "claimed"
DEAD = "dead"

Clock = Callable[[], float]
IdFactory = Callable[[], str]


class JobQueueError(ValueError):
    """Raised on malformed input or an unknown job."""


class StaleLease(JobQueueError):  # noqa: N818
    """Raised when an ack/nack presents a token that is no longer the job's claim."""


@dataclass(frozen=True)
class Job:
    """A claimed unit of work handed to a worker."""

    id: str
    payload: bytes
    attempts: int
    lease_token: int


@dataclass
class _Record:
    id: str
    payload: bytes
    attempts: int = 0
    status: str = AVAILABLE
    deadline: float = 0.0
    token: int = 0
    seq: int = 0  # enqueue order, for FIFO claiming


def _seq_ids() -> IdFactory:
    counter = {"n": 0}

    def factory() -> str:
        counter["n"] += 1
        return f"job-{counter['n']:08d}"

    return factory


class JobQueue:
    """An in-memory durable work queue with visibility leases and fencing tokens."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        clock: Clock = time.monotonic,
        id_factory: IdFactory | None = None,
    ) -> None:
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts <= 0:
            raise JobQueueError("max_attempts must be a positive int")  # noqa: TRY003
        self._max_attempts = max_attempts
        self._clock = clock
        self._id = id_factory or _seq_ids()
        self._jobs: dict[str, _Record] = {}
        self._token = 0
        self._seq = 0

    def enqueue(self, payload: bytes) -> str:
        if not isinstance(payload, (bytes, bytearray)):
            raise JobQueueError("payload must be bytes")  # noqa: TRY003
        job_id = self._id()
        self._seq += 1
        self._jobs[job_id] = _Record(id=job_id, payload=bytes(payload), seq=self._seq)
        return job_id

    def _get(self, job_id: str) -> _Record:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise JobQueueError(f"unknown job: {job_id!r}") from None  # noqa: TRY003

    def _next_token(self) -> int:
        self._token += 1
        return self._token

    def claim(self, *, lease: float) -> Job | None:
        """Claim the oldest available job under a visibility lease, or None."""
        if not isinstance(lease, (int, float)) or isinstance(lease, bool) or lease <= 0:
            raise JobQueueError("lease must be a positive number of seconds")  # noqa: TRY003
        available = [r for r in self._jobs.values() if r.status == AVAILABLE]
        if not available:
            return None
        record = min(available, key=lambda r: r.seq)  # FIFO
        record.status = CLAIMED
        record.token = self._next_token()
        record.deadline = self._clock() + lease
        return Job(
            id=record.id, payload=record.payload, attempts=record.attempts, lease_token=record.token
        )

    def _require_current(self, record: _Record, lease_token: int) -> None:
        if record.status != CLAIMED or record.token != lease_token:
            raise StaleLease(f"lease {lease_token} for job {record.id!r} is no longer current")  # noqa: TRY003

    def ack(self, job_id: str, lease_token: int) -> None:
        """Mark a claimed job done. A stale token (lease lost) raises StaleLease."""
        record = self._get(job_id)
        self._require_current(record, lease_token)
        del self._jobs[job_id]

    def nack(self, job_id: str, lease_token: int) -> str:
        """Release a claimed job for retry, or dead-letter at max_attempts; returns the status."""
        record = self._get(job_id)
        self._require_current(record, lease_token)
        record.attempts += 1
        if record.attempts >= self._max_attempts:
            record.status = DEAD
        else:
            record.status = AVAILABLE
            record.deadline = 0.0
        return record.status

    def reclaim_expired(self) -> int:
        """Redeliver every claimed job whose lease has elapsed. Returns the count."""
        now = self._clock()
        reclaimed = 0
        for record in self._jobs.values():
            if record.status == CLAIMED and record.deadline <= now:
                record.status = AVAILABLE
                record.deadline = 0.0
                record.token = self._next_token()  # fence: invalidate the old worker's token
                reclaimed += 1
        return reclaimed

    def stats(self) -> dict[str, int]:
        out = {AVAILABLE: 0, CLAIMED: 0, DEAD: 0}
        for record in self._jobs.values():
            out[record.status] += 1
        return out
