"""Portable, reviewable contracts for the CodeForge script platform."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    VALIDATING = "validating"
    TESTABLE = "testable"
    TESTING = "testing"
    REVIEW = "review"
    APPROVED = "approved"
    STAGED = "staged"
    ACTIVE = "active"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    DISABLED = "disabled"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    DEPRECATED = "deprecated"


class LifecycleError(ValueError):
    """A script lifecycle transition is invalid or not independently authorized."""


_TRANSITIONS: dict[LifecycleStatus, frozenset[LifecycleStatus]] = {
    LifecycleStatus.DRAFT: frozenset({LifecycleStatus.VALIDATING}),
    LifecycleStatus.VALIDATING: frozenset({LifecycleStatus.DRAFT, LifecycleStatus.TESTABLE}),
    LifecycleStatus.TESTABLE: frozenset({LifecycleStatus.TESTING}),
    LifecycleStatus.TESTING: frozenset({LifecycleStatus.DRAFT, LifecycleStatus.REVIEW}),
    LifecycleStatus.REVIEW: frozenset({LifecycleStatus.DRAFT, LifecycleStatus.APPROVED}),
    LifecycleStatus.APPROVED: frozenset({LifecycleStatus.STAGED}),
    LifecycleStatus.STAGED: frozenset({LifecycleStatus.DRAFT, LifecycleStatus.ACTIVE}),
    LifecycleStatus.ACTIVE: frozenset(
        {LifecycleStatus.DEGRADED, LifecycleStatus.QUARANTINED, LifecycleStatus.SUPERSEDED}
    ),
    LifecycleStatus.DEGRADED: frozenset({LifecycleStatus.ACTIVE, LifecycleStatus.DISABLED}),
    LifecycleStatus.QUARANTINED: frozenset({LifecycleStatus.DISABLED, LifecycleStatus.ACTIVE}),
    LifecycleStatus.DISABLED: frozenset({LifecycleStatus.DEPRECATED}),
    LifecycleStatus.SUPERSEDED: frozenset({LifecycleStatus.ROLLED_BACK}),
    LifecycleStatus.ROLLED_BACK: frozenset({LifecycleStatus.ACTIVE}),
    LifecycleStatus.DEPRECATED: frozenset(),
}


@dataclass(frozen=True)
class ResourcePolicy:
    """Per-invocation limits.  ``network`` is intentionally deny-by-default."""

    cpu_ms: int = 25
    wall_ms: int = 100
    memory_bytes: int = 16 * 1024 * 1024
    stack_bytes: int = 1024 * 1024
    output_bytes: int = 8192
    log_events: int = 100
    host_calls: int = 64
    state_reads: int = 64
    state_writes: int = 16
    spawned_tasks: int = 0
    open_files: int = 0
    network: str = "deny"

    def __post_init__(self) -> None:
        for name in (
            "cpu_ms",
            "wall_ms",
            "memory_bytes",
            "stack_bytes",
            "output_bytes",
            "log_events",
            "host_calls",
            "state_reads",
            "state_writes",
            "spawned_tasks",
            "open_files",
        ):
            if not isinstance(getattr(self, name), int) or getattr(self, name) < 0:
                raise ValueError(f"resource {name} must be a non-negative integer")
        if self.cpu_ms == 0 or self.wall_ms == 0 or self.memory_bytes == 0:
            raise ValueError("cpu_ms, wall_ms, and memory_bytes must be positive")
        if self.network not in {"deny", "allowlist"}:
            raise ValueError("network must be 'deny' or 'allowlist'")

    def to_dict(self) -> dict[str, object]:
        return {
            "cpu_ms": self.cpu_ms,
            "wall_ms": self.wall_ms,
            "memory_bytes": self.memory_bytes,
            "stack_bytes": self.stack_bytes,
            "output_bytes": self.output_bytes,
            "log_events": self.log_events,
            "host_calls": self.host_calls,
            "state_reads": self.state_reads,
            "state_writes": self.state_writes,
            "spawned_tasks": self.spawned_tasks,
            "open_files": self.open_files,
            "network": self.network,
        }


_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,127}$")


@dataclass(frozen=True)
class ScriptManifest:
    """The authoritative description of one immutable source revision."""

    script_id: str
    version: str
    language: str
    source_hash: str
    source_revision: int
    entrypoints: Mapping[str, str]
    seed_ids: tuple[str, ...]
    object_types: tuple[str, ...]
    capabilities: frozenset[str]
    state_schema_version: int = 1
    state_schema_ref: str | None = None
    resource_policy: ResourcePolicy = field(default_factory=ResourcePolicy)
    compatibility: str = "*"
    provenance_id: str = ""
    owner_id: str = ""
    review_status: str = "draft"
    localization_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("script_id", "version", "language", "source_hash"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.source_revision, int) or self.source_revision < 1:
            raise ValueError("source_revision must be a positive integer")
        if self.state_schema_version < 1:
            raise ValueError("state_schema_version must be positive")
        object.__setattr__(self, "entrypoints", dict(self.entrypoints))
        object.__setattr__(self, "seed_ids", tuple(self.seed_ids))
        object.__setattr__(self, "object_types", tuple(self.object_types))
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        object.__setattr__(self, "localization_keys", tuple(self.localization_keys))

    def to_dict(self) -> dict[str, object]:
        return {
            "script_id": self.script_id,
            "version": self.version,
            "language": self.language,
            "source": {"revision": self.source_revision, "sha256": self.source_hash},
            "entrypoints": [
                {"event": event, "function": function}
                for event, function in sorted(self.entrypoints.items())
            ],
            "scope": {"seed_ids": list(self.seed_ids), "object_types": list(self.object_types)},
            "capabilities": sorted(self.capabilities),
            "resources": self.resource_policy.to_dict(),
            "state": {
                "schema_version": self.state_schema_version,
                "schema_ref": self.state_schema_ref,
            },
            "compatibility": {"script_api": self.compatibility},
            "provenance": {"id": self.provenance_id, "owner": self.owner_id},
            "review": {"status": self.review_status},
            "localization_keys": list(self.localization_keys),
        }


@dataclass(frozen=True)
class ScriptSandbox:
    """Recorded runner policy; it is metadata, not a claim that OS isolation exists."""

    sandbox_id: str
    runner: str
    runner_version: str
    network: str = "deny"
    filesystem: str = "deny"
    health: str = "healthy"


@dataclass(frozen=True)
class Attachment:
    """Stable object-to-revision binding; executable source never lives in an object row."""

    attachment_id: str
    object_id: str
    script_id: str
    script_version: str
    entrypoint: str
    seed_id: str
    priority: int = 100
    enabled: bool = True
    state_partition: str = ""


@dataclass(frozen=True)
class _LifecycleEvent:
    actor_id: str
    status: LifecycleStatus
    reason: str


class LifecycleManager:
    """Small in-memory lifecycle authority suitable for a durable store adapter."""

    def __init__(self, script_id: str, *, actor_id: str = "system") -> None:
        if not _ID.fullmatch(script_id):
            raise LifecycleError("script_id must be a stable lowercase identifier")
        self.script_id = script_id
        self.status = LifecycleStatus.DRAFT
        self.history: list[_LifecycleEvent] = [_LifecycleEvent(actor_id, self.status, "created")]

    def transition(
        self,
        target: LifecycleStatus | str,
        *,
        actor_id: str,
        reason: str = "",
        independent_approval: bool = False,
    ) -> LifecycleStatus:
        try:
            target_status = LifecycleStatus(target)
        except ValueError as exc:
            raise LifecycleError(f"unknown lifecycle status: {target}") from exc
        if target_status not in _TRANSITIONS[self.status]:
            raise LifecycleError(f"cannot move script from {self.status} to {target_status}")
        if not actor_id.strip():
            raise LifecycleError("actor_id must not be empty")
        if target_status == LifecycleStatus.ACTIVE and not independent_approval:
            raise LifecycleError("activation requires an independent approval")
        self.status = target_status
        self.history.append(_LifecycleEvent(actor_id, target_status, reason))
        return self.status
