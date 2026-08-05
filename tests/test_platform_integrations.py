"""Aggregate twin for small platform integration adapters."""

import json

from kernel.shelf.outbox import OutboxRecord
from kernel.world import bus
from kernel.world.outbox_relay import _publish
from kernel.world.workshop_state import load_changes, save_changes


def test_workshop_state_round_trip_and_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEFORGE_WORKSHOP_STATE", str(tmp_path / "workshop.json"))
    changes = [
        {"kind": "create_item", "payload": {"label": "lantern", "name": "Lantern", "room": "spawn"}}
    ]

    save_changes("aethryn", changes)

    assert load_changes("aethryn") == changes


def test_outbox_relay_publishes_json_objects(monkeypatch):
    seen = []
    monkeypatch.setattr(
        bus.get_bus(), "publish", lambda topic, payload: seen.append((topic, payload))
    )
    record = OutboxRecord(id=1, topic="platform.test", payload=json.dumps({"ok": True}).encode())

    _publish(record)

    assert seen == [("platform.test", {"ok": True})]
