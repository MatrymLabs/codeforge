"""Durable, owner-authenticated implementation tasks for a SeedLab workspace."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kernel.shelf.atomic_write import atomic_write_text

TASK_READY = "ready"
_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class TaskError(ValueError):
    """A task is invalid, duplicated with different content, or cannot be persisted."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    seed_id: str
    owner_id: str
    title: str
    description: str
    source_proposal: str
    evidence_ids: tuple[str, ...] = ()
    status: str = TASK_READY
    created_at: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        if not _TASK_ID.fullmatch(self.task_id):
            raise TaskError("task_id must be 1-120 characters of letters, numbers, '.', '_' or '-'")
        for name in ("seed_id", "owner_id", "title", "description"):
            if not str(getattr(self, name)).strip():
                raise TaskError(f"{name} must not be empty")
        if self.status != TASK_READY:
            raise TaskError(f"unsupported task status: {self.status}")
        if not self.created_at.strip():
            object.__setattr__(self, "created_at", _now())
        object.__setattr__(self, "evidence_ids", tuple(str(item) for item in self.evidence_ids))

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "seed_id": self.seed_id,
            "owner_id": self.owner_id,
            "title": self.title,
            "description": self.description,
            "source_proposal": self.source_proposal,
            "evidence_ids": list(self.evidence_ids),
            "status": self.status,
            "created_at": self.created_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> TaskRecord:
        evidence = raw.get("evidence_ids", [])
        if not isinstance(evidence, list):
            raise TaskError("evidence_ids must be a list")
        version = raw.get("version", 1)
        if not isinstance(version, int) or isinstance(version, bool):
            raise TaskError("version must be an integer")
        return cls(
            task_id=str(raw["task_id"]),
            seed_id=str(raw["seed_id"]),
            owner_id=str(raw["owner_id"]),
            title=str(raw["title"]),
            description=str(raw["description"]),
            source_proposal=str(raw.get("source_proposal", "")),
            evidence_ids=tuple(str(item) for item in evidence),
            status=str(raw.get("status", TASK_READY)),
            created_at=str(raw.get("created_at", "")),
            version=version,
        )


class FileTaskStore:
    """Atomic JSON-backed task store; creation is idempotent for identical task content."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._tasks: dict[str, TaskRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise TaskError("task store must contain a list")
            self._tasks = {
                task.task_id: task for task in (TaskRecord.from_dict(item) for item in raw)
            }
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            TaskError,
        ) as exc:
            raise TaskError(f"cannot load task store {self.path}: {exc}") from exc

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path,
            json.dumps([task.to_dict() for task in self._tasks.values()], indent=2, sort_keys=True)
            + "\n",
        )

    def create(self, task: TaskRecord) -> TaskRecord:
        existing = self._tasks.get(task.task_id)
        if existing is not None:
            existing_content = existing.to_dict()
            requested_content = task.to_dict()
            existing_content.pop("created_at", None)
            requested_content.pop("created_at", None)
            if existing_content == requested_content:
                return existing
            raise TaskError(f"task already exists with different content: {task.task_id}")
        self._tasks[task.task_id] = task
        self._persist()
        return task

    def all_for_seed(self, seed_id: str) -> tuple[TaskRecord, ...]:
        return tuple(task for task in self._tasks.values() if task.seed_id == seed_id)


def configured_task_store(root: Path) -> FileTaskStore:
    return FileTaskStore(Path(root) / "tasks.json")
