"""World-assembly wiring for the durable SQL outbox relay."""

from __future__ import annotations

import json

from kernel.shelf.outbox import OutboxRecord, SqlOutbox, schedule_sql_relay
from kernel.world import bus

_INSTALLED = False


def _publish(record: OutboxRecord) -> None:
    payload = json.loads(record.payload.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("outbox payload must be a JSON object")
    bus.get_bus().publish(record.topic, payload)


def register() -> None:
    """Attach one durable relay to the canonical world beat."""
    global _INSTALLED
    if _INSTALLED:
        return
    schedule_sql_relay(SqlOutbox(), _publish)
    _INSTALLED = True
