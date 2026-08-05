from __future__ import annotations

import json

from kernel.shelf.outbox import SqlOutbox, schedule_sql_relay, sql_relay
from kernel.world import climate, scheduler
from kernel.world.db import _ENGINES


def test_sql_outbox_relay_and_beat_schedule(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "outbox.db"
    monkeypatch.setenv("CODEFORGE_DB", str(db_path))
    _ENGINES.clear()
    outbox = SqlOutbox()
    record = outbox.stage("delivery:test", json.dumps({"id": 1}).encode())
    seen: list[tuple[str, bytes]] = []
    assert sql_relay(outbox, lambda row: seen.append((row.topic, row.payload))).sent == 1
    assert seen == [("delivery:test", b'{"id": 1}')]
    assert outbox.counts()["sent"] == 1

    scheduler.clear()
    climate.reset()
    pending = outbox.stage("delivery:scheduled", b"{}")
    schedule_sql_relay(outbox, lambda _row: None, every_beats=1)
    climate.advance()
    scheduler.run_due(climate.now())
    assert outbox.counts()["sent"] == 2
    assert pending.id != record.id
