"""Small, original containment service for persistent Seed entities.

This is an experiment, not a replacement for Aethryn inventory stores. It provides stable
identity, owner authorization, cycle prevention, snapshots, and deterministic traversal so a
future persistent adapter can implement the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass


class ContainmentError(ValueError):
    """A containment operation would violate identity, ownership, or graph invariants."""


@dataclass(frozen=True)
class ContainmentRecord:
    entity_id: str
    owner_id: str
    parent_id: str | None = None
    version: int = 0


class ContainmentService:
    """An owner-authorized, cycle-safe in-memory containment graph."""

    def __init__(self) -> None:
        self._records: dict[str, ContainmentRecord] = {}

    def register(self, entity_id: str, owner_id: str) -> ContainmentRecord:
        if not entity_id.strip() or not owner_id.strip():
            raise ContainmentError("entity_id and owner_id must not be empty")
        if entity_id in self._records:
            raise ContainmentError(f"entity already registered: {entity_id}")
        record = ContainmentRecord(entity_id, owner_id)
        self._records[entity_id] = record
        return record

    def get(self, entity_id: str) -> ContainmentRecord:
        try:
            return self._records[entity_id]
        except KeyError as exc:
            raise ContainmentError(f"unknown entity: {entity_id}") from exc

    def move(self, entity_id: str, parent_id: str | None, *, actor_id: str) -> ContainmentRecord:
        record = self.get(entity_id)
        if record.owner_id != actor_id:
            raise ContainmentError(f"actor {actor_id!r} does not own entity {entity_id!r}")
        if parent_id is not None:
            parent = self.get(parent_id)
            if parent.owner_id != actor_id:
                raise ContainmentError("actor must own the destination container")
            if parent_id == entity_id or entity_id in self.ancestors(parent_id):
                raise ContainmentError("containment cycle refused")
        updated = ContainmentRecord(entity_id, record.owner_id, parent_id, record.version + 1)
        self._records[entity_id] = updated
        return updated

    def children(self, parent_id: str) -> tuple[ContainmentRecord, ...]:
        self.get(parent_id)
        return tuple(record for record in self._records.values() if record.parent_id == parent_id)

    def ancestors(self, entity_id: str) -> tuple[str, ...]:
        current = self.get(entity_id)
        result: list[str] = []
        seen: set[str] = set()
        while current.parent_id is not None:
            if current.parent_id in seen:
                raise ContainmentError("containment graph is corrupt")
            seen.add(current.parent_id)
            result.append(current.parent_id)
            current = self.get(current.parent_id)
        return tuple(result)

    def snapshot(self) -> dict[str, ContainmentRecord]:
        return dict(self._records)

    def restore(self, snapshot: dict[str, ContainmentRecord], *, actor_id: str) -> None:
        if any(record.owner_id != actor_id for record in snapshot.values()):
            raise ContainmentError("actor cannot restore another owner's containment")
        candidate = ContainmentService()
        candidate._records = dict(snapshot)
        for entity_id in candidate._records:
            candidate.ancestors(entity_id)
        self._records = dict(snapshot)
