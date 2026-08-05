"""CARD: outbox -- stage a message with the state change; a relay publishes it at-least-once.

Clean-room reconstruction of the Transactional Outbox pattern. Standard library
only.

The dual-write problem: a database commit and a broker publish cannot be atomic,
so a crash between them loses an event or emits a phantom. The outbox stages the
message in the SAME unit of work as the state change (one commit), and a separate
relay publishes staged messages at-least-once and marks them sent exactly once.
Consumers must be idempotent (compose with the fleet's idempotency part).

This module is the reference mechanism with an in-memory store; production backs
OutboxRecord in a table and calls stage() inside the state-change transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

PENDING = "pending"
SENT = "sent"
DEAD = "dead"


class OutboxError(ValueError):
    """Raised on malformed input or an unknown record id."""


# An id factory returns a unique record id; a clock returns a monotonic-ish stamp.
IdFactory = Callable[[], str]
Clock = Callable[[], float]
Publish = Callable[["OutboxRecord"], None]


@dataclass
class OutboxRecord:
    id: str
    topic: str
    payload: bytes
    status: str = PENDING
    attempts: int = 0
    created_at: float = 0.0


def _seq_ids() -> IdFactory:
    counter = {"n": 0}

    def factory() -> str:
        counter["n"] += 1
        return f"obx-{counter['n']:08d}"

    return factory


def _zero_clock() -> float:
    return 0.0


@dataclass
class RelaySummary:
    sent: int = 0
    failed: int = 0
    dead: int = 0


class Outbox:
    """A reference outbox store. Records are staged pending, relayed to sent/dead."""

    def __init__(self, *, id_factory: IdFactory | None = None, clock: Clock = _zero_clock) -> None:
        self._records: dict[str, OutboxRecord] = {}
        self._order: list[str] = []
        self._id = id_factory or _seq_ids()
        self._clock = clock

    def stage(self, topic: str, payload: bytes) -> OutboxRecord:
        """Stage a message. In production this runs inside the state-change transaction."""
        if not isinstance(topic, str) or topic.strip() == "":
            raise OutboxError("topic must be a non-empty string")
        if not isinstance(payload, (bytes, bytearray)):
            raise OutboxError("payload must be bytes")
        record = OutboxRecord(
            id=self._id(),
            topic=topic,
            payload=bytes(payload),
            status=PENDING,
            attempts=0,
            created_at=self._clock(),
        )
        self._records[record.id] = record
        self._order.append(record.id)
        return record

    def get(self, record_id: str) -> OutboxRecord:
        try:
            return self._records[record_id]
        except KeyError:
            raise OutboxError(f"unknown outbox record: {record_id!r}") from None

    def unsent(self) -> list[OutboxRecord]:
        """Pending records in stage order (the relay's work list)."""
        return [self._records[i] for i in self._order if self._records[i].status == PENDING]

    def mark_sent(self, record_id: str) -> None:
        """Idempotent: marking a sent record again is a no-op."""
        record = self.get(record_id)
        if record.status == DEAD:
            raise OutboxError(f"cannot mark a dead record sent: {record_id!r}")
        record.status = SENT

    def mark_failed(self, record_id: str, *, max_attempts: int) -> str:
        """Record a failed publish attempt; route to dead at the bound. Returns new status."""
        if not isinstance(max_attempts, int) or max_attempts <= 0:
            raise OutboxError("max_attempts must be a positive int")
        record = self.get(record_id)
        if record.status != PENDING:
            return record.status
        record.attempts += 1
        if record.attempts >= max_attempts:
            record.status = DEAD
        return record.status

    def counts(self) -> dict[str, int]:
        out = {PENDING: 0, SENT: 0, DEAD: 0}
        for record in self._records.values():
            out[record.status] += 1
        return out


class SqlOutbox:
    """SQL-backed outbox for production state changes.

    ``stage_in`` accepts a caller-owned SQLAlchemy session so the event row can
    commit atomically with the business mutation. ``stage`` is the convenient
    standalone form for callers that have no surrounding transaction.
    """

    def stage(self, topic: str, payload: bytes, *, session: Any = None) -> OutboxRecord:
        from kernel.world.db import OutboxRow, open_archive_session

        if not isinstance(topic, str) or not topic.strip():
            raise OutboxError("topic must be a non-empty string")
        if not isinstance(payload, (bytes, bytearray)):
            raise OutboxError("payload must be bytes")
        import secrets
        import time

        record = OutboxRecord(
            id=f"obx-{secrets.token_hex(12)}",
            topic=topic,
            payload=bytes(payload),
            created_at=time.time(),
        )
        owns_session = session is None
        db = session or open_archive_session()
        db.add(
            OutboxRow(
                id=record.id,
                topic=record.topic,
                payload=record.payload,
                status=record.status,
                attempts=record.attempts,
                created_at=record.created_at,
            )
        )
        if owns_session:
            db.commit()
            db.close()
        return record

    def unsent(self, *, session: Any = None) -> list[OutboxRecord]:
        from kernel.world.db import OutboxRow, open_archive_session

        owns_session = session is None
        db = session or open_archive_session()
        rows = (
            db.query(OutboxRow)
            .filter(OutboxRow.status == PENDING)
            .order_by(OutboxRow.created_at, OutboxRow.id)
            .all()
        )
        if owns_session:
            db.close()
        return [
            OutboxRecord(r.id, r.topic, bytes(r.payload), r.status, r.attempts, r.created_at)
            for r in rows
        ]

    def mark_sent(self, record_id: str) -> None:
        from kernel.world.db import OutboxRow, open_archive_session

        with open_archive_session() as db:
            row = db.get(OutboxRow, record_id)
            if row is None:
                raise OutboxError(f"unknown outbox record: {record_id!r}")
            if row.status == DEAD:
                raise OutboxError(f"cannot mark a dead record sent: {record_id!r}")
            row.status = SENT
            db.commit()

    def mark_failed(self, record_id: str, *, max_attempts: int) -> str:
        from kernel.world.db import OutboxRow, open_archive_session

        if not isinstance(max_attempts, int) or max_attempts <= 0:
            raise OutboxError("max_attempts must be a positive int")
        with open_archive_session() as db:
            row = db.get(OutboxRow, record_id)
            if row is None:
                raise OutboxError(f"unknown outbox record: {record_id!r}")
            if row.status != PENDING:
                return row.status
            row.attempts += 1
            if row.attempts >= max_attempts:
                row.status = DEAD
            db.commit()
            return row.status

    def counts(self) -> dict[str, int]:
        from kernel.world.db import OutboxRow, open_archive_session

        with open_archive_session() as db:
            rows = db.query(OutboxRow.status).all()
        counts = {PENDING: 0, SENT: 0, DEAD: 0}
        for (status,) in rows:
            counts[status] = counts.get(status, 0) + 1
        return counts


def sql_relay(
    outbox: SqlOutbox,
    publish: Publish,
    *,
    batch: int = 100,
    max_attempts: int = 5,
) -> RelaySummary:
    """Relay durable rows using the same at-least-once contract as the reference store."""

    if not isinstance(batch, int) or batch <= 0:
        raise OutboxError("batch must be a positive int")
    summary = RelaySummary()
    for record in outbox.unsent()[:batch]:
        try:
            publish(record)
        except Exception:  # noqa: BLE001 - failed delivery is retriable data
            status = outbox.mark_failed(record.id, max_attempts=max_attempts)
            if status == DEAD:
                summary.dead += 1
            else:
                summary.failed += 1
        else:
            outbox.mark_sent(record.id)
            summary.sent += 1
    return summary


def schedule_sql_relay(
    outbox: SqlOutbox,
    publish: Publish,
    *,
    every_beats: int = 1,
    batch: int = 100,
    max_attempts: int = 5,
) -> None:
    """Attach a durable relay to the canonical world beat.

    The scheduler remains the only clock in the engine; no background worker is
    introduced. A caller wires the process's bus publisher once at startup.
    """

    if not isinstance(every_beats, int) or every_beats <= 0:
        raise OutboxError("every_beats must be a positive int")
    from kernel.world import climate, scheduler

    scheduler.schedule(
        climate.now() + every_beats,
        lambda: sql_relay(outbox, publish, batch=batch, max_attempts=max_attempts),
        every=every_beats,
    )


def relay(
    outbox: Outbox,
    publish: Publish,
    *,
    batch: int = 100,
    max_attempts: int = 5,
) -> RelaySummary:
    """Publish unsent records at-least-once. Mark sent on success, retry on failure,
    route to dead at max_attempts. A publish that raises is caught, never propagated.
    """
    if not isinstance(batch, int) or batch <= 0:
        raise OutboxError("batch must be a positive int")
    if not isinstance(max_attempts, int) or max_attempts <= 0:
        raise OutboxError("max_attempts must be a positive int")
    summary = RelaySummary()
    for record in outbox.unsent()[:batch]:
        try:
            publish(record)
        except Exception:  # a failed publish is data, not a crash; retry next pass
            status = outbox.mark_failed(record.id, max_attempts=max_attempts)
            if status == DEAD:
                summary.dead += 1
            else:
                summary.failed += 1
        else:
            outbox.mark_sent(record.id)
            summary.sent += 1
    return summary
