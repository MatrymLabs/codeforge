"""Durable replay storage for validated Seed event envelopes."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from kernel.event_envelope import EventEnvelope


class EventReplayError(ValueError):
    """A replay record is malformed, duplicated, or cannot be addressed."""


class EventReplayStore:
    """Protocol-like base for durable event replay implementations."""

    def append(self, event: EventEnvelope) -> None:  # pragma: no cover - interface guard
        raise NotImplementedError

    def replay(
        self, *, after_event_id: str | None = None, limit: int = 100
    ) -> tuple[EventEnvelope, ...]:
        raise NotImplementedError


@dataclass
class InMemoryEventReplayStore(EventReplayStore):
    """Deterministic replay store for isolated tests."""

    _events: list[EventEnvelope] = field(default_factory=list)

    def append(self, event: EventEnvelope) -> None:
        if any(existing.event_id == event.event_id for existing in self._events):
            raise EventReplayError(f"duplicate event id: {event.event_id}")
        self._events.append(event)

    def replay(
        self, *, after_event_id: str | None = None, limit: int = 100
    ) -> tuple[EventEnvelope, ...]:
        if limit <= 0:
            raise EventReplayError("replay limit must be positive")
        start = 0
        if after_event_id is not None:
            matches = [
                index
                for index, event in enumerate(self._events)
                if event.event_id == after_event_id
            ]
            if not matches:
                raise EventReplayError(f"unknown replay cursor: {after_event_id}")
            start = matches[0] + 1
        return tuple(self._events[start : start + limit])


@dataclass
class FileEventReplayStore(EventReplayStore):
    """Append-only JSONL event store with cursor-based replay across restart."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[EventEnvelope]:
        if not self.path.is_file():
            return []
        events: list[EventEnvelope] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise TypeError("event record must be an object")
                events.append(EventEnvelope.from_dict(raw))
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            EventReplayError,
        ) as exc:
            raise EventReplayError(f"cannot read replay store {self.path}: {exc}") from exc
        ids = [event.event_id for event in events]
        if len(ids) != len(set(ids)):
            raise EventReplayError(f"duplicate event ids in replay store {self.path}")
        return events

    def append(self, event: EventEnvelope) -> None:
        if any(existing.event_id == event.event_id for existing in self._read()):
            raise EventReplayError(f"duplicate event id: {event.event_id}")
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise EventReplayError(f"cannot append replay store {self.path}: {exc}") from exc

    def replay(
        self, *, after_event_id: str | None = None, limit: int = 100
    ) -> tuple[EventEnvelope, ...]:
        if limit <= 0:
            raise EventReplayError("replay limit must be positive")
        events = self._read()
        start = 0
        if after_event_id is not None:
            matches = [
                index for index, event in enumerate(events) if event.event_id == after_event_id
            ]
            if not matches:
                raise EventReplayError(f"unknown replay cursor: {after_event_id}")
            start = matches[0] + 1
        return tuple(events[start : start + limit])


def append_all(store: EventReplayStore, events: Iterable[EventEnvelope]) -> None:
    """Append a batch through the same duplicate and validation checks as single events."""
    for event in events:
        store.append(event)
