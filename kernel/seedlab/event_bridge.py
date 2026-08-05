"""Bridge typed Seed events onto CodeForge's existing message bus and audit ledger.

This is an additive adapter. It does not replace the world Frame/GMCP path; it gives
SeedLab jobs and Workshop services a versioned event topic that can later be consumed
by the Master Client, Creator Console, or a broker-backed bus.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from kernel.event_envelope import EventEnvelope
from kernel.world import audit, bus

SEED_EVENT_TOPIC = "codeforge:seed-event"
EventHandler = Callable[[EventEnvelope], None]


def _decode(payload: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope.from_dict(payload)


def publish_seed_event(event: EventEnvelope, *, audit_event: bool = True) -> None:
    """Publish one validated event and optionally append its correlation to the audit ledger."""
    payload = event.to_dict()
    bus.get_bus().publish(SEED_EVENT_TOPIC, payload)
    if audit_event:
        audit.record(
            event.session_id,
            event.event_type,
            json.dumps(
                {
                    "event_id": event.event_id,
                    "correlation_id": event.correlation_id,
                    "seed_id": event.seed_id,
                },
                sort_keys=True,
            ),
            ts=event.timestamp,
        )


def subscribe_seed_events(handler: EventHandler) -> Callable[[], None]:
    """Subscribe to typed events; return an idempotent unsubscribe closure."""

    def receive(payload: dict[str, Any]) -> None:
        handler(_decode(payload))

    bus.get_bus().subscribe(SEED_EVENT_TOPIC, receive)
    active = True

    def unsubscribe() -> None:
        nonlocal active
        if active:
            bus.get_bus().unsubscribe(SEED_EVENT_TOPIC, receive)
            active = False

    return unsubscribe
