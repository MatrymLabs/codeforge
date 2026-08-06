"""Durable migration and rollback records for governed Hardware components.

This module owns the evidence boundary around a version change. It does not execute component
source: callers provide the already-approved migration, health, and compensation functions.
"""

from __future__ import annotations

import fcntl
import json
import secrets
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from kernel.hardware_lifecycle import HardwareLifecycleError, HardwareRecord, HardwareRegistry
from kernel.permission_policy import PermissionContext, PermissionPolicy
from kernel.shelf.atomic_write import atomic_write_text

MIGRATION_COMPLETED = "completed"
MIGRATION_FAILED = "failed"
MIGRATION_ROLLED_BACK = "rolled_back"
ROLLBACK_COMPLETED = "completed"
ROLLBACK_FAILED = "failed"


class HardwareMigrationError(HardwareLifecycleError):
    """A migration or its required compensation could not be completed safely."""


class MigrationBackup(Protocol):
    """The minimal verified-backup authority a component migration may use."""

    def verify(self, reference: str) -> None: ...

    def restore(self, reference: str) -> None: ...


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _mint(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


def _required(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HardwareMigrationError(f"{field} must not be empty")
    return value.strip()


@dataclass(frozen=True)
class MigrationRecord:
    """Durable evidence for one component version migration attempt."""

    migration_id: str
    component_id: str
    seed_id: str
    from_version: str
    to_version: str
    backup_reference: str
    status: str
    preconditions: tuple[str, ...]
    health: str
    operator_decision: str
    authorization: str = ""
    compensation: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "migration_id",
            "component_id",
            "seed_id",
            "from_version",
            "to_version",
            "backup_reference",
            "status",
            "health",
            "operator_decision",
        ):
            _required(getattr(self, field_name), field_name)
        object.__setattr__(self, "preconditions", tuple(self.preconditions))

    def to_dict(self) -> dict[str, object]:
        return {
            "migration_id": self.migration_id,
            "component_id": self.component_id,
            "seed_id": self.seed_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "backup_reference": self.backup_reference,
            "status": self.status,
            "preconditions": list(self.preconditions),
            "health": self.health,
            "operator_decision": self.operator_decision,
            "authorization": self.authorization,
            "compensation": self.compensation,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


@dataclass(frozen=True)
class RollbackRecord:
    """Durable evidence for compensation of a failed component migration."""

    rollback_id: str
    migration_id: str
    component_id: str
    seed_id: str
    from_version: str
    to_version: str
    backup_reference: str
    trigger: str
    status: str
    health: str
    operator_decision: str
    started_at: str = ""
    completed_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "rollback_id": self.rollback_id,
            "migration_id": self.migration_id,
            "component_id": self.component_id,
            "seed_id": self.seed_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "backup_reference": self.backup_reference,
            "trigger": self.trigger,
            "status": self.status,
            "health": self.health,
            "operator_decision": self.operator_decision,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


@dataclass
class HardwareMigrationJournal:
    """File-backed, immutable-by-ID storage for migration and rollback evidence."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        (self.root / "migrations").mkdir(parents=True, exist_ok=True)
        (self.root / "rollbacks").mkdir(parents=True, exist_ok=True)
        (self.root / "locks").mkdir(parents=True, exist_ok=True)

    @contextmanager
    def exclusive(self, component_id: str):
        """Serialize one component's migration across threads and OS processes."""
        safe_component = _required(component_id, "component_id")
        lock_path = self.root / "locks" / f"{safe_component}.lock"
        with lock_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def save_migration(self, record: MigrationRecord) -> None:
        self._save("migrations", record.migration_id, record.to_dict(), replace=True)

    def save_rollback(self, record: RollbackRecord) -> None:
        self._save("rollbacks", record.rollback_id, record.to_dict())

    def load_migration(self, migration_id: str) -> MigrationRecord:
        raw = self._load("migrations", migration_id)
        try:
            raw_preconditions = raw["preconditions"]
            if not isinstance(raw_preconditions, list):
                raise TypeError("preconditions must be a list")
            return MigrationRecord(
                migration_id=str(raw["migration_id"]),
                component_id=str(raw["component_id"]),
                seed_id=str(raw["seed_id"]),
                from_version=str(raw["from_version"]),
                to_version=str(raw["to_version"]),
                backup_reference=str(raw["backup_reference"]),
                status=str(raw["status"]),
                preconditions=tuple(str(item) for item in raw_preconditions),
                health=str(raw["health"]),
                operator_decision=str(raw["operator_decision"]),
                authorization=str(raw.get("authorization", "")),
                compensation=str(raw.get("compensation", "")),
                started_at=str(raw.get("started_at", "")),
                completed_at=str(raw.get("completed_at", "")),
                error=str(raw.get("error", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HardwareMigrationError(f"malformed migration record: {exc}") from exc

    def load_rollback(self, rollback_id: str) -> RollbackRecord:
        raw = self._load("rollbacks", rollback_id)
        try:
            return RollbackRecord(
                rollback_id=str(raw["rollback_id"]),
                migration_id=str(raw["migration_id"]),
                component_id=str(raw["component_id"]),
                seed_id=str(raw["seed_id"]),
                from_version=str(raw["from_version"]),
                to_version=str(raw["to_version"]),
                backup_reference=str(raw["backup_reference"]),
                trigger=str(raw["trigger"]),
                status=str(raw["status"]),
                health=str(raw["health"]),
                operator_decision=str(raw["operator_decision"]),
                started_at=str(raw.get("started_at", "")),
                completed_at=str(raw.get("completed_at", "")),
                error=str(raw.get("error", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HardwareMigrationError(f"malformed rollback record: {exc}") from exc

    def _save(
        self,
        category: str,
        record_id: str,
        payload: dict[str, object],
        *,
        replace: bool = False,
    ) -> None:
        target = self.root / category / f"{_required(record_id, 'record_id')}.json"
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if target.is_file():
            if not replace and target.read_text(encoding="utf-8") != encoded:
                raise HardwareMigrationError(f"{record_id!r} already has different evidence")
            if not replace:
                return
        atomic_write_text(target, encoded)

    def _load(self, category: str, record_id: str) -> dict[str, object]:
        target = self.root / category / f"{_required(record_id, 'record_id')}.json"
        if not target.is_file():
            raise HardwareMigrationError(f"unknown {category[:-1]} record: {record_id!r}")
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HardwareMigrationError(f"cannot read {target}: {exc}") from exc
        if not isinstance(raw, dict):
            raise HardwareMigrationError(f"{target} must contain an object")
        return raw


MigrationStep = Callable[[HardwareRecord], None]
HealthCheck = Callable[[HardwareRecord], bool]


def _serialize_migration(
    function: Callable[..., MigrationRecord],
) -> Callable[..., MigrationRecord]:
    """Hold the component lock for the complete read/mutate/health/rollback sequence."""
    from functools import wraps

    @wraps(function)
    def locked(
        registry: HardwareRegistry,
        journal: HardwareMigrationJournal,
        component_id: str,
        to_version: str,
        *args: object,
        **kwargs: object,
    ) -> MigrationRecord:
        with journal.exclusive(component_id):
            return function(
                registry,
                journal,
                component_id,
                to_version,
                *args,
                **kwargs,
            )

    return locked


@_serialize_migration
def migrate_hardware_component(
    registry: HardwareRegistry,
    journal: HardwareMigrationJournal,
    component_id: str,
    to_version: str,
    *,
    seed_id: str,
    backup_reference: str,
    preconditions: tuple[str, ...],
    operator_decision: str,
    migrate: MigrationStep,
    health_check: HealthCheck,
    compensate: MigrationStep,
    backup: MigrationBackup | None = None,
    policy: PermissionPolicy | None = None,
    permission: PermissionContext | None = None,
    clock: Callable[[], str] = _utcnow,
    id_minter: Callable[[str], str] = _mint,
) -> MigrationRecord:
    """Run a version migration with durable failure compensation and health evidence."""
    current = registry.get(component_id)
    if current is None:
        raise HardwareMigrationError(f"component {component_id!r} is not discovered")
    if current.state not in {"installed", "active", "disabled"}:
        raise HardwareMigrationError(f"component {component_id!r} is not migration-ready")
    if not to_version.strip() or to_version == current.version:
        raise HardwareMigrationError("migration target version must differ and not be empty")
    if not preconditions:
        raise HardwareMigrationError("migration requires named preconditions")
    _required(seed_id, "seed_id")
    _required(backup_reference, "backup_reference")
    _required(operator_decision, "operator_decision")
    if (policy is None) != (permission is None):
        raise HardwareMigrationError("policy and permission must be supplied together")
    authorization = ""
    if policy is not None and permission is not None:
        try:
            policy.require(
                permission,
                capability="hardware.migrate",
                scope=seed_id,
            )
        except Exception as exc:
            raise HardwareMigrationError(f"migration authorization refused: {exc}") from exc
        authorization = "authorized:hardware.migrate"
    if backup is not None:
        try:
            backup.verify(backup_reference)
        except Exception as exc:
            raise HardwareMigrationError(f"migration backup verification failed: {exc}") from exc

    migration_id = id_minter("migration")
    started = clock()
    base = MigrationRecord(
        migration_id=migration_id,
        component_id=component_id,
        seed_id=seed_id,
        from_version=current.version,
        to_version=to_version,
        backup_reference=backup_reference,
        status="started",
        preconditions=preconditions,
        health="unknown",
        operator_decision=operator_decision,
        authorization=authorization,
        started_at=started,
    )
    journal.save_migration(base)
    try:
        migrate(current)
        updated = registry.update_version(component_id, to_version)
        healthy = health_check(updated)
        if not healthy:
            raise HardwareMigrationError("post-migration health check failed")
    except Exception as exc:
        compensation_error = ""
        try:
            if backup is not None:
                backup.restore(backup_reference)
            else:
                compensate(current)
            registry.update_version(component_id, current.version)
            rollback = RollbackRecord(
                rollback_id=id_minter("rollback"),
                migration_id=migration_id,
                component_id=component_id,
                seed_id=seed_id,
                from_version=current.version,
                to_version=to_version,
                backup_reference=backup_reference,
                trigger=str(exc),
                status=ROLLBACK_COMPLETED,
                health="healthy",
                operator_decision=operator_decision,
                started_at=clock(),
                completed_at=clock(),
            )
            journal.save_rollback(rollback)
            final = MigrationRecord(
                **{
                    **base.__dict__,
                    "status": MIGRATION_ROLLED_BACK,
                    "health": "healthy",
                    "compensation": rollback.rollback_id,
                    "completed_at": clock(),
                    "error": str(exc),
                }
            )
            journal.save_migration(final)
            return final
        except Exception as rollback_exc:
            compensation_error = str(rollback_exc)
        final = MigrationRecord(
            **{
                **base.__dict__,
                "status": MIGRATION_FAILED,
                "health": "unknown",
                "completed_at": clock(),
                "error": f"{exc}; compensation failed: {compensation_error}",
            }
        )
        journal.save_migration(final)
        raise HardwareMigrationError(final.error) from exc

    final = MigrationRecord(
        **{
            **base.__dict__,
            "status": MIGRATION_COMPLETED,
            "health": "healthy",
            "completed_at": clock(),
        }
    )
    journal.save_migration(final)
    return final
