"""Governed CreatorDraft lifecycle for Workshop authoring.

Draft payloads are isolated data. They do not mutate live Seed state; publication is an
explicit reviewed transition after validation and approval.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kernel.shelf.atomic_write import atomic_write_text

CREATED, VALIDATED, SIMULATED, REVIEW, APPROVED, PUBLISHED, OBSERVED, ROLLED_BACK, REJECTED = (
    "created",
    "validated",
    "simulated",
    "review",
    "approved",
    "published",
    "observed",
    "rolled_back",
    "rejected",
)
_TRANSITIONS = {
    CREATED: {VALIDATED, REJECTED},
    VALIDATED: {SIMULATED, REVIEW, REJECTED},
    SIMULATED: {REVIEW, REJECTED},
    REVIEW: {APPROVED, REJECTED},
    APPROVED: {PUBLISHED, REJECTED},
    PUBLISHED: {OBSERVED, ROLLED_BACK},
    OBSERVED: {ROLLED_BACK},
    ROLLED_BACK: set(),
    REJECTED: set(),
}


class CreatorDraftError(ValueError):
    """A draft mutation or lifecycle transition is invalid."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DraftAudit:
    actor_id: str
    action: str
    when: str


@dataclass(frozen=True)
class CreatorDraft:
    draft_id: str
    seed_id: str
    owner_id: str
    payload: Mapping[str, object]
    status: str = CREATED
    version: int = 1
    audit: tuple[DraftAudit, ...] = ()

    def __post_init__(self) -> None:
        for field in ("draft_id", "seed_id", "owner_id"):
            if not str(getattr(self, field)).strip():
                raise CreatorDraftError(f"{field} must not be empty")
        if self.status not in _TRANSITIONS:
            raise CreatorDraftError(f"unknown draft status: {self.status}")
        object.__setattr__(self, "payload", dict(self.payload))

    def edit(self, actor_id: str, changes: Mapping[str, object]) -> CreatorDraft:
        if actor_id != self.owner_id:
            raise CreatorDraftError("only the draft owner may edit a draft")
        if self.status != CREATED:
            raise CreatorDraftError("only a created draft may be edited")
        updated = dict(self.payload)
        updated.update(changes)
        return CreatorDraft(
            self.draft_id,
            self.seed_id,
            self.owner_id,
            updated,
            self.status,
            self.version + 1,
            self.audit + (DraftAudit(actor_id, "edited", _now()),),
        )

    def transition(self, target: str, actor_id: str) -> CreatorDraft:
        if target not in _TRANSITIONS.get(self.status, set()):
            raise CreatorDraftError(f"cannot move draft from {self.status} to {target}")
        if target == PUBLISHED and actor_id == self.owner_id:
            raise CreatorDraftError("publication requires an independent approver")
        if target in {VALIDATED, REVIEW} and actor_id != self.owner_id:
            raise CreatorDraftError("owner must perform draft validation/review submission")
        return CreatorDraft(
            self.draft_id,
            self.seed_id,
            self.owner_id,
            self.payload,
            target,
            self.version + 1,
            self.audit + (DraftAudit(actor_id, f"transition:{target}", _now()),),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe durable representation of the draft and its audit trail."""
        return {
            "draft_id": self.draft_id,
            "seed_id": self.seed_id,
            "owner_id": self.owner_id,
            "payload": dict(self.payload),
            "status": self.status,
            "version": self.version,
            "audit": [
                {"actor_id": entry.actor_id, "action": entry.action, "when": entry.when}
                for entry in self.audit
            ],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> CreatorDraft:
        """Restore a draft without silently repairing malformed persisted state."""
        try:
            payload = raw["payload"]
            audit = raw.get("audit", [])
            if not isinstance(payload, Mapping) or not isinstance(audit, list):
                raise TypeError("payload must be a mapping and audit must be a list")
            entries = tuple(
                DraftAudit(
                    actor_id=str(entry["actor_id"]),
                    action=str(entry["action"]),
                    when=str(entry["when"]),
                )
                for entry in audit
                if isinstance(entry, Mapping)
            )
            if len(entries) != len(audit):
                raise TypeError("audit entries must be mappings")
            version = raw.get("version", 1)
            if not isinstance(version, int):
                raise TypeError("version must be an integer")
            return cls(
                draft_id=str(raw["draft_id"]),
                seed_id=str(raw["seed_id"]),
                owner_id=str(raw["owner_id"]),
                payload=dict(payload),
                status=str(raw.get("status", CREATED)),
                version=version,
                audit=entries,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CreatorDraftError(f"malformed persisted draft: {exc}") from exc


@dataclass
class CreatorDraftStore:
    """A volatile draft store for the first contract slice."""

    _drafts: dict[str, CreatorDraft]

    def __init__(self) -> None:
        self._drafts = {}

    def create(self, draft: CreatorDraft) -> CreatorDraft:
        if draft.draft_id in self._drafts:
            raise CreatorDraftError(f"duplicate draft: {draft.draft_id}")
        self._drafts[draft.draft_id] = draft
        return draft

    def get(self, draft_id: str) -> CreatorDraft:
        try:
            return self._drafts[draft_id]
        except KeyError as exc:
            raise CreatorDraftError(f"unknown draft: {draft_id}") from exc

    def save(self, draft: CreatorDraft) -> CreatorDraft:
        self.get(draft.draft_id)
        self._drafts[draft.draft_id] = draft
        return draft


@dataclass
class FileCreatorDraftStore(CreatorDraftStore):
    """Atomic JSON-backed draft store used by a durable Creator Workshop."""

    path: Path = Path("creator-drafts.json")

    def __init__(self, path: Path):
        super().__init__()
        self.path = Path(path)
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise TypeError("draft store must contain a list")
            self._drafts = {
                draft.draft_id: draft for draft in (CreatorDraft.from_dict(item) for item in raw)
            }
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            CreatorDraftError,
        ) as exc:
            raise CreatorDraftError(f"cannot load draft store {self.path}: {exc}") from exc

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path,
            json.dumps(
                [draft.to_dict() for draft in self._drafts.values()],
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    def create(self, draft: CreatorDraft) -> CreatorDraft:
        value = super().create(draft)
        self._persist()
        return value

    def save(self, draft: CreatorDraft) -> CreatorDraft:
        value = super().save(draft)
        self._persist()
        return value
