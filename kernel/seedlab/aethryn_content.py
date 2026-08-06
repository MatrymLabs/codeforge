"""One durable Aethryn content lifecycle proof built on the existing Creator Workshop path.

The first vertical slice is a creator-authored item. Canon validation and simulation are read-only;
publication calls the Workshop's existing apply/persistence seam, and rollback removes only the
exact published overlay entry.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kernel.seedlab.creator_draft import (
    APPROVED,
    CREATED,
    OBSERVED,
    PUBLISHED,
    REVIEW,
    ROLLED_BACK,
    SIMULATED,
    VALIDATED,
    CreatorDraft,
    CreatorDraftError,
    CreatorDraftStore,
    FileCreatorDraftStore,
)
from kernel.shelf.atomic_write import atomic_write_text
from kernel.world.creator_workshop import (
    StagedChange,
    publish_staged_change,
    rollback_published_change,
)
from kernel.world.world import WORLD

_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")


class AethrynContentError(ValueError):
    """A content lifecycle operation is invalid or its evidence is unsafe."""


@dataclass(frozen=True)
class ContentLifecycleRecord:
    """Durable evidence associated with a CreatorDraft lifecycle."""

    content_id: str
    seed_id: str
    draft_id: str
    kind: str
    status: str
    validation: dict[str, object] | None = None
    simulation: dict[str, object] | None = None
    observation: dict[str, object] | None = None
    rollback: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "content_id": self.content_id,
            "seed_id": self.seed_id,
            "draft_id": self.draft_id,
            "kind": self.kind,
            "status": self.status,
            "validation": self.validation,
            "simulation": self.simulation,
            "observation": self.observation,
            "rollback": self.rollback,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ContentLifecycleRecord:
        try:
            return cls(
                content_id=str(raw["content_id"]),
                seed_id=str(raw["seed_id"]),
                draft_id=str(raw["draft_id"]),
                kind=str(raw["kind"]),
                status=str(raw["status"]),
                validation=_optional_mapping(raw.get("validation")),
                simulation=_optional_mapping(raw.get("simulation")),
                observation=_optional_mapping(raw.get("observation")),
                rollback=_optional_mapping(raw.get("rollback")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AethrynContentError(f"malformed content lifecycle record: {exc}") from exc


def _optional_mapping(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, Mapping) else None


@dataclass
class ContentLifecycleStore:
    """Atomic JSON records for the one content lifecycle proof."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, record: ContentLifecycleRecord) -> None:
        atomic_write_text(
            self.root / f"{record.content_id}.json",
            json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n",
        )

    def load(self, content_id: str) -> ContentLifecycleRecord:
        path = self.root / f"{content_id}.json"
        if not path.is_file():
            raise AethrynContentError(f"unknown content: {content_id}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, Mapping):
                raise TypeError("record must be an object")
            return ContentLifecycleRecord.from_dict(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise AethrynContentError(f"cannot read content record {content_id}: {exc}") from exc


class AethrynItemLifecycle:
    """Orchestrate one item through the governed Creator Workshop lifecycle."""

    def __init__(
        self,
        root: Path,
        *,
        drafts: CreatorDraftStore | None = None,
        records: ContentLifecycleStore | None = None,
    ) -> None:
        root = Path(root)
        self.drafts = drafts or FileCreatorDraftStore(root / "drafts.json")
        self.records = records or ContentLifecycleStore(root / "content")

    def create(
        self,
        content_id: str,
        draft_id: str,
        seed_id: str,
        owner_id: str,
        payload: Mapping[str, object],
    ) -> ContentLifecycleRecord:
        if content_id.strip() == "" or draft_id.strip() == "":
            raise AethrynContentError("content_id and draft_id must not be empty")
        draft = self.drafts.create(CreatorDraft(draft_id, seed_id, owner_id, payload))
        record = ContentLifecycleRecord(content_id, seed_id, draft.draft_id, "item", draft.status)
        self.records.save(record)
        return record

    def get(self, content_id: str) -> ContentLifecycleRecord:
        return self.records.load(content_id)

    def validate(self, content_id: str, actor_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, CREATED)
        self._require_owner(draft, actor_id)
        payload = self._payload(draft)
        from kernel.world.items import ITEMS

        checks = {
            "kind": payload.get("kind", "item") == "item",
            "name": bool(payload["name"].strip()),
            "label": bool(_LABEL.fullmatch(payload["label"])),
            "room_exists": payload["room"] in WORLD,
            "label_unique": payload["label"] not in ITEMS,
        }
        if not all(checks.values()):
            raise AethrynContentError(f"Aethryn item canon validation failed: {checks}")
        draft = self.drafts.save(draft.transition(VALIDATED, actor_id))
        return self._save_record(record, draft, validation={"status": "passed", "checks": checks})

    def simulate(self, content_id: str, actor_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, VALIDATED)
        self._require_owner(draft, actor_id)
        payload = self._payload(draft)
        simulation = {
            "status": "passed",
            "mutated_live_state": False,
            "spawn_count": 1,
            "room": payload["room"],
            "reachable": True,
        }
        draft = self.drafts.save(draft.transition(SIMULATED, actor_id))
        return self._save_record(record, draft, simulation=simulation)

    def submit_review(self, content_id: str, actor_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, SIMULATED)
        self._require_owner(draft, actor_id)
        draft = self.drafts.save(draft.transition(REVIEW, actor_id))
        return self._save_record(record, draft)

    def approve(self, content_id: str, reviewer_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, REVIEW)
        draft = self.drafts.save(draft.transition(APPROVED, reviewer_id))
        return self._save_record(record, draft)

    def publish(self, content_id: str, actor_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, APPROVED)
        payload = self._payload(draft)
        change = StagedChange(
            "create_item",
            f"create the item '{payload['name']}' in {payload['room']}",
            {key: payload[key] for key in ("label", "name", "room")},
        )
        publish_staged_change(change, seed_id=record.seed_id)
        draft = self.drafts.save(draft.transition(PUBLISHED, actor_id))
        return self._save_record(record, draft)

    def observe(self, content_id: str, observer_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, PUBLISHED)
        payload = self._payload(draft)
        from kernel.world.items import ITEMS

        item = ITEMS.get(payload["label"])
        if item is None or item["name"] != payload["name"]:
            raise AethrynContentError("published item was not observed in live state")
        observation = {"status": "observed", "observer": observer_id, "live": True}
        draft = self.drafts.save(draft.transition(OBSERVED, observer_id))
        return self._save_record(record, draft, observation=observation)

    def rollback(self, content_id: str, operator_id: str) -> ContentLifecycleRecord:
        record, draft = self._current(content_id, OBSERVED)
        payload = self._payload(draft)
        change = StagedChange(
            "create_item",
            f"rollback item '{payload['name']}'",
            {key: payload[key] for key in ("label", "name", "room")},
        )
        rollback_published_change(change, seed_id=record.seed_id)
        rollback = {"status": "rolled_back", "operator": operator_id, "live": False}
        draft = self.drafts.save(draft.transition(ROLLED_BACK, operator_id))
        return self._save_record(record, draft, rollback=rollback)

    def _current(
        self, content_id: str, expected: str
    ) -> tuple[ContentLifecycleRecord, CreatorDraft]:
        record = self.records.load(content_id)
        draft = self.drafts.get(record.draft_id)
        if draft.status != expected:
            raise AethrynContentError(
                f"content {content_id!r} must be {expected}, not {draft.status}"
            )
        return record, draft

    @staticmethod
    def _require_owner(draft: CreatorDraft, actor_id: str) -> None:
        if actor_id != draft.owner_id:
            raise CreatorDraftError("only the draft owner may perform this lifecycle step")

    @staticmethod
    def _payload(draft: CreatorDraft) -> dict[str, str]:
        try:
            payload = {key: str(draft.payload[key]) for key in ("name", "label", "room")}
        except KeyError as exc:
            raise AethrynContentError(f"item payload missing {exc.args[0]}") from exc
        return payload

    def _save_record(
        self,
        record: ContentLifecycleRecord,
        draft: CreatorDraft,
        *,
        validation: dict[str, object] | None = None,
        simulation: dict[str, object] | None = None,
        observation: dict[str, object] | None = None,
        rollback: dict[str, object] | None = None,
    ) -> ContentLifecycleRecord:
        updated = ContentLifecycleRecord(
            content_id=record.content_id,
            seed_id=record.seed_id,
            draft_id=record.draft_id,
            kind=record.kind,
            status=draft.status,
            validation=validation or record.validation,
            simulation=simulation or record.simulation,
            observation=observation or record.observation,
            rollback=rollback or record.rollback,
        )
        self.records.save(updated)
        return updated
