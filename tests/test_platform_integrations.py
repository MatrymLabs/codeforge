"""Aggregate twin for small platform integration adapters."""

import json

import pytest

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


def test_workshop_draft_state_rejects_malformed_owner_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEFORGE_WORKSHOP_DRAFTS", str(tmp_path / "drafts.json"))
    (tmp_path / "drafts.json").write_text(
        '{"version": 1, "owners": {"owner": [{"kind": "create_npc", "payload": {}}]}}',
        encoding="utf-8",
    )

    from kernel.world.workshop_state import WorkshopStateError, load_drafts

    with pytest.raises(WorkshopStateError, match="invalid metadata"):
        load_drafts("aethryn")


def test_outbox_relay_publishes_json_objects(monkeypatch):
    seen = []
    monkeypatch.setattr(
        bus.get_bus(), "publish", lambda topic, payload: seen.append((topic, payload))
    )
    record = OutboxRecord(id=1, topic="platform.test", payload=json.dumps({"ok": True}).encode())

    _publish(record)

    assert seen == [("platform.test", {"ok": True})]
