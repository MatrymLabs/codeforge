"""A small desired-state deployment controller for local Seed artifacts.

This is deliberately local and file-backed. It proves the lifecycle contract needed by the Seed
platform before introducing a cloud scheduler: stage an exact artifact, run a named health check,
atomically point the profile at the healthy release, persist evidence, and roll back to the prior
release. The controller never executes artifact code or accepts shell commands.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.shelf.atomic_write import atomic_write_text

if TYPE_CHECKING:
    from kernel.seedlab.artifact_store import ArtifactRecord

DEPLOYED = "deployed"
FAILED = "failed"
ROLLED_BACK = "rolled_back"
_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


class DeploymentError(ValueError):
    """A deployment profile or local deployment transition is invalid."""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _safe(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or not _SAFE.fullmatch(value.strip()):
        raise DeploymentError(f"{field} must be a safe non-empty identifier")
    return value.strip()


@dataclass(frozen=True)
class DeploymentProfile:
    """Desired state for one local artifact deployment."""

    profile_id: str
    seed_id: str
    artifact_id: str
    artifact_path: str
    health_check: str = "artifact-present"
    target: str = "local"
    correlation_id: str = ""
    operator_id: str = ""
    artifact_evidence_id: str = ""
    backup_reference: str = ""

    def __post_init__(self) -> None:
        _safe(self.profile_id, "profile_id")
        _safe(self.seed_id, "seed_id")
        _safe(self.artifact_id, "artifact_id")
        if self.target != "local":
            raise DeploymentError("the first deployment adapter supports only target 'local'")
        if not self.artifact_path.strip():
            raise DeploymentError("artifact_path must not be empty")
        if not self.health_check.strip():
            raise DeploymentError("health_check must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "seed_id": self.seed_id,
            "artifact_id": self.artifact_id,
            "artifact_path": self.artifact_path,
            "health_check": self.health_check,
            "target": self.target,
            "correlation_id": self.correlation_id,
            "operator_id": self.operator_id,
            "artifact_evidence_id": self.artifact_evidence_id,
            "backup_reference": self.backup_reference,
        }


@dataclass(frozen=True)
class DeploymentRun:
    """Durable evidence for one desired-state reconciliation attempt."""

    run_id: str
    profile_id: str
    seed_id: str
    artifact_id: str
    status: str
    release_path: str
    previous_release: str = ""
    health: str = "unknown"
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    correlation_id: str = ""
    operator_id: str = ""
    artifact_evidence_id: str = ""
    backup_reference: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "seed_id": self.seed_id,
            "artifact_id": self.artifact_id,
            "status": self.status,
            "release_path": self.release_path,
            "previous_release": self.previous_release,
            "health": self.health,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "correlation_id": self.correlation_id,
            "operator_id": self.operator_id,
            "artifact_evidence_id": self.artifact_evidence_id,
            "backup_reference": self.backup_reference,
        }

    @classmethod
    def from_dict(cls, raw: object) -> DeploymentRun:
        if not isinstance(raw, dict):
            raise DeploymentError("deployment run must be an object")
        try:
            return cls(
                run_id=str(raw["run_id"]),
                profile_id=str(raw["profile_id"]),
                seed_id=str(raw["seed_id"]),
                artifact_id=str(raw["artifact_id"]),
                status=str(raw["status"]),
                release_path=str(raw.get("release_path", "")),
                previous_release=str(raw.get("previous_release", "")),
                health=str(raw.get("health", "unknown")),
                started_at=str(raw.get("started_at", "")),
                completed_at=str(raw.get("completed_at", "")),
                error=str(raw.get("error", "")),
                correlation_id=str(raw.get("correlation_id", "")),
                operator_id=str(raw.get("operator_id", "")),
                artifact_evidence_id=str(raw.get("artifact_evidence_id", "")),
                backup_reference=str(raw.get("backup_reference", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DeploymentError(f"malformed deployment run: {exc}") from exc


@dataclass(frozen=True)
class DeploymentBackup:
    """Exact release and optional state snapshot used by local recovery."""

    backup_id: str
    profile_id: str
    seed_id: str
    artifact_id: str
    release_path: str
    release_digest: str
    state_path: str = ""
    state_digest: str = ""
    state_is_dir: bool = False
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "backup_id": self.backup_id,
            "profile_id": self.profile_id,
            "seed_id": self.seed_id,
            "artifact_id": self.artifact_id,
            "release_path": self.release_path,
            "release_digest": self.release_digest,
            "state_path": self.state_path,
            "state_digest": self.state_digest,
            "state_is_dir": self.state_is_dir,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, raw: object) -> DeploymentBackup:
        if not isinstance(raw, dict):
            raise DeploymentError("deployment backup must be an object")
        try:
            return cls(
                backup_id=str(raw["backup_id"]),
                profile_id=str(raw["profile_id"]),
                seed_id=str(raw["seed_id"]),
                artifact_id=str(raw["artifact_id"]),
                release_path=str(raw["release_path"]),
                release_digest=str(raw["release_digest"]),
                state_path=str(raw.get("state_path", "")),
                state_digest=str(raw.get("state_digest", "")),
                state_is_dir=bool(raw.get("state_is_dir", False)),
                created_at=str(raw.get("created_at", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DeploymentError(f"malformed deployment backup: {exc}") from exc


HealthCheck = Callable[[Path], bool]


def artifact_present(path: Path) -> bool:
    """The minimal local health check: a staged artifact is a non-empty directory."""
    return path.is_dir() and any(path.iterdir())


def _tree_digest(path: Path) -> str:
    if path.is_file():
        files = (path,)
        prefix = path.name
    elif path.is_dir():
        files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
        prefix = ""
    else:
        raise DeploymentError(f"backup path does not exist: {path}")
    digest = hashlib.sha256()
    for item in files:
        relative = item.name if prefix else item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class LocalDeploymentController:
    """Reconcile local deployment profiles with durable, rollback-capable releases."""

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], str] = _utcnow,
        id_minter: Callable[[], str] | None = None,
        health_checks: dict[str, HealthCheck] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.id_minter = id_minter or (lambda: f"deploy-{secrets.token_hex(4)}")
        self.health_checks = {"artifact-present": artifact_present, **(health_checks or {})}

    def _profile_root(self, profile_id: str) -> Path:
        return self.root / _safe(profile_id, "profile_id")

    def _current_path(self, profile_id: str) -> Path:
        return self._profile_root(profile_id) / "current.json"

    def _run_path(self, run_id: str) -> Path:
        return self.root / "runs" / f"{_safe(run_id, 'run_id')}.json"

    def _backup_path(self, profile_id: str, backup_id: str) -> Path:
        safe_profile = _safe(profile_id, "profile_id")
        safe_backup = _safe(backup_id, "backup_id")
        return self.root / "backups" / safe_profile / safe_backup

    def _backup_record_path(self, profile_id: str, backup_id: str) -> Path:
        return self._backup_path(profile_id, backup_id) / "backup.json"

    def _read_current(self, profile_id: str) -> str:
        path = self._current_path(profile_id)
        if not path.is_file():
            return ""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return str(raw["release_path"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DeploymentError(
                f"cannot read current deployment for {profile_id!r}: {exc}"
            ) from exc

    def _save_run(self, run: DeploymentRun) -> None:
        path = self._run_path(run.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n")

    def get_run(self, run_id: str) -> DeploymentRun:
        path = self._run_path(run_id)
        if not path.is_file():
            raise DeploymentError(f"unknown deployment run: {run_id}")
        try:
            return DeploymentRun.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeploymentError(f"cannot read deployment run {run_id!r}: {exc}") from exc

    def current_release(self, profile_id: str) -> Path | None:
        current = self._read_current(profile_id)
        if not current:
            return None
        path = Path(current).resolve()
        try:
            path.relative_to(self._profile_root(profile_id).resolve())
        except ValueError as exc:
            raise DeploymentError("current release escapes the profile root") from exc
        return path if path.is_dir() else None

    def backup_current(
        self,
        profile_id: str,
        *,
        seed_id: str,
        artifact_id: str,
        state_path: Path | None = None,
        backup_id: str | None = None,
    ) -> DeploymentBackup:
        """Snapshot the exact deployed release and optional mutable state."""
        release = self.current_release(profile_id)
        if release is None:
            raise DeploymentError("cannot back up a profile without a current release")
        backup_id = _safe(backup_id or f"backup-{secrets.token_hex(4)}", "backup_id")
        destination = self._backup_path(profile_id, backup_id)
        if destination.exists():
            raise DeploymentError(f"backup already exists: {backup_id}")
        destination.mkdir(parents=True)
        release_copy = destination / "release"
        shutil.copytree(release, release_copy)
        state_copy = ""
        state_digest = ""
        state_is_dir = False
        if state_path is not None:
            state = Path(state_path).resolve()
            if not state.exists():
                raise DeploymentError(f"state path does not exist: {state_path}")
            state_copy_path = destination / "state"
            state_is_dir = state.is_dir()
            if state.is_dir():
                shutil.copytree(state, state_copy_path)
            else:
                state_copy_path.mkdir()
                shutil.copy2(state, state_copy_path / state.name)
            state_copy = str(state_copy_path)
            state_digest = _tree_digest(state)
        backup = DeploymentBackup(
            backup_id=backup_id,
            profile_id=_safe(profile_id, "profile_id"),
            seed_id=_safe(seed_id, "seed_id"),
            artifact_id=_safe(artifact_id, "artifact_id"),
            release_path=str(release_copy),
            release_digest=_tree_digest(release_copy),
            state_path=state_copy,
            state_digest=state_digest,
            state_is_dir=state_is_dir,
            created_at=self.clock(),
        )
        atomic_write_text(
            self._backup_record_path(profile_id, backup_id),
            json.dumps(backup.to_dict(), indent=2, sort_keys=True) + "\n",
        )
        return backup

    def get_backup(self, profile_id: str, backup_id: str) -> DeploymentBackup:
        path = self._backup_record_path(profile_id, backup_id)
        if not path.is_file():
            raise DeploymentError(f"unknown deployment backup: {backup_id}")
        try:
            return DeploymentBackup.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeploymentError(f"cannot read deployment backup {backup_id!r}: {exc}") from exc

    def verify_backup(self, profile_id: str, backup_id: str) -> DeploymentBackup:
        backup = self.get_backup(profile_id, backup_id)
        if _tree_digest(Path(backup.release_path)) != backup.release_digest:
            raise DeploymentError("deployment backup release digest does not match")
        if backup.state_path and _tree_digest(Path(backup.state_path)) != backup.state_digest:
            raise DeploymentError("deployment backup state digest does not match")
        return backup

    def restore_backup(
        self, profile_id: str, backup_id: str, *, state_path: Path | None = None
    ) -> DeploymentRun:
        """Restore a verified release/state snapshot and record the recovery transition."""
        backup = self.verify_backup(profile_id, backup_id)
        profile_root = self._profile_root(profile_id)
        release_root = profile_root / "releases"
        release_root.mkdir(parents=True, exist_ok=True)
        restored = release_root / f"restore-{_safe(backup_id, 'backup_id')}"
        if restored.exists():
            shutil.rmtree(restored)
        shutil.copytree(backup.release_path, restored)
        if state_path is not None:
            if not backup.state_path:
                raise DeploymentError("backup has no state snapshot")
            target = Path(state_path).resolve()
            source = Path(backup.state_path)
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            if backup.state_is_dir:
                shutil.copytree(source, target)
            else:
                first = next(source.iterdir())
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(first, target)
        previous = self._read_current(profile_id)
        atomic_write_text(
            self._current_path(profile_id),
            json.dumps(
                {
                    "profile_id": profile_id,
                    "artifact_id": backup.artifact_id,
                    "release_path": str(restored),
                },
                sort_keys=True,
            )
            + "\n",
        )
        run = DeploymentRun(
            run_id=_safe(self.id_minter(), "run_id"),
            profile_id=profile_id,
            seed_id=backup.seed_id,
            artifact_id=backup.artifact_id,
            status=ROLLED_BACK,
            release_path=str(restored),
            previous_release=previous,
            health="healthy",
            started_at=self.clock(),
            completed_at=self.clock(),
            backup_reference=backup.backup_id,
        )
        self._save_run(run)
        return run

    def deploy(self, profile: DeploymentProfile) -> DeploymentRun:
        """Stage, health-check, and atomically promote one local artifact."""
        source = Path(profile.artifact_path).resolve()
        if not source.is_dir():
            raise DeploymentError(f"artifact path is not a directory: {profile.artifact_path}")
        profile_root = self._profile_root(profile.profile_id)
        profile_root.mkdir(parents=True, exist_ok=True)
        release_root = profile_root / "releases"
        staging_root = profile_root / ".staging"
        release_root.mkdir(exist_ok=True)
        staging_root.mkdir(exist_ok=True)
        run_id = _safe(self.id_minter(), "run_id")
        started = self.clock()
        previous = self._read_current(profile.profile_id)
        staged = staging_root / run_id
        release = release_root / run_id
        check = self.health_checks.get(profile.health_check)
        if check is None:
            raise DeploymentError(f"unknown health check: {profile.health_check!r}")
        try:
            shutil.copytree(source, staged)
            healthy = check(staged)
            if not healthy:
                raise DeploymentError(f"health check {profile.health_check!r} failed")
            staged.replace(release)
            atomic_write_text(
                self._current_path(profile.profile_id),
                json.dumps(
                    {
                        "profile_id": profile.profile_id,
                        "artifact_id": profile.artifact_id,
                        "release_path": str(release),
                    },
                    sort_keys=True,
                )
                + "\n",
            )
            run = DeploymentRun(
                run_id=run_id,
                profile_id=profile.profile_id,
                seed_id=profile.seed_id,
                artifact_id=profile.artifact_id,
                status=DEPLOYED,
                release_path=str(release),
                previous_release=previous,
                health="healthy",
                started_at=started,
                completed_at=self.clock(),
                correlation_id=profile.correlation_id,
                operator_id=profile.operator_id,
                artifact_evidence_id=profile.artifact_evidence_id,
                backup_reference=profile.backup_reference,
            )
        except (OSError, DeploymentError) as exc:
            shutil.rmtree(staged, ignore_errors=True)
            run = DeploymentRun(
                run_id=run_id,
                profile_id=profile.profile_id,
                seed_id=profile.seed_id,
                artifact_id=profile.artifact_id,
                status=FAILED,
                release_path=str(release),
                previous_release=previous,
                health="unhealthy",
                started_at=started,
                completed_at=self.clock(),
                error=str(exc),
                correlation_id=profile.correlation_id,
                operator_id=profile.operator_id,
                artifact_evidence_id=profile.artifact_evidence_id,
                backup_reference=profile.backup_reference,
            )
        self._save_run(run)
        return run

    def rollback(self, run_id: str) -> DeploymentRun:
        """Restore the prior healthy release recorded by a successful deployment."""
        deployed = self.get_run(run_id)
        if deployed.status != DEPLOYED or not deployed.previous_release:
            raise DeploymentError("deployment has no prior release to roll back to")
        previous = Path(deployed.previous_release).resolve()
        profile_root = self._profile_root(deployed.profile_id).resolve()
        try:
            previous.relative_to(profile_root)
        except ValueError as exc:
            raise DeploymentError("rollback release escapes the profile root") from exc
        if not previous.is_dir():
            raise DeploymentError("rollback release is missing")
        atomic_write_text(
            self._current_path(deployed.profile_id),
            json.dumps(
                {
                    "profile_id": deployed.profile_id,
                    "artifact_id": "previous-release",
                    "release_path": str(previous),
                },
                sort_keys=True,
            )
            + "\n",
        )
        rollback = DeploymentRun(
            run_id=_safe(self.id_minter(), "run_id"),
            profile_id=deployed.profile_id,
            seed_id=deployed.seed_id,
            artifact_id="previous-release",
            status=ROLLED_BACK,
            release_path=str(previous),
            previous_release=deployed.release_path,
            health="healthy",
            started_at=self.clock(),
            completed_at=self.clock(),
            correlation_id=deployed.correlation_id,
            operator_id=deployed.operator_id,
            artifact_evidence_id=deployed.artifact_evidence_id,
            backup_reference=deployed.backup_reference,
        )
        self._save_run(rollback)
        return rollback


@dataclass(frozen=True)
class DeploymentMigrationBackup:
    """Verified backup adapter for Hardware migrations targeting a local deployment."""

    controller: LocalDeploymentController
    profile_id: str
    state_path: Path | None = None

    def verify(self, reference: str) -> None:
        """Refuse a migration unless the referenced release and state bytes still verify."""
        self.controller.verify_backup(self.profile_id, reference)

    def restore(self, reference: str) -> None:
        """Restore the exact release/state snapshot and persist the deployment recovery run."""
        self.controller.restore_backup(
            self.profile_id,
            reference,
            state_path=self.state_path,
        )


def deploy_verified_artifact(
    controller: LocalDeploymentController,
    profile: DeploymentProfile,
    artifact: ArtifactRecord,
) -> DeploymentRun:
    """Enter deployment only through an artifact record with complete required evidence."""
    if artifact.seed_id != profile.seed_id or artifact.artifact_id != profile.artifact_id:
        raise DeploymentError("deployment profile does not match the artifact evidence")
    if not artifact.deployment_eligible:
        raise DeploymentError("artifact is not deployment-eligible: required evidence is missing")
    if profile.artifact_evidence_id and profile.artifact_evidence_id != artifact.artifact_id:
        raise DeploymentError("deployment profile artifact evidence does not match")
    if not profile.backup_reference.strip():
        raise DeploymentError("deployment requires a verified backup reference")
    return controller.deploy(profile)
