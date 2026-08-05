"""Join a validated Seed manifest to a real Workshop job and durable evidence.

This is intentionally an adapter over the existing SeedLab stores. It does not create a
second Seed loader, job runner, Hardware registry, or event bus. The caller must explicitly
activate required Hardware before this adapter will run a job.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.event_envelope import EventEnvelope
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.seedlab.jobs import DEFAULT_TIMEOUT, OUTPUT_CAP, JobRecord
from kernel.seedlab.workshop_services import CreatorWorkshopService
from kernel.shelf.atomic_write import atomic_write_text


class ManifestEvidenceError(ValueError):
    """A manifest could not be validated or its evidence could not be recovered."""


@dataclass(frozen=True)
class SeedManifest:
    """The smallest validated input needed for a governed SeedLab test.

    ``SeedRecord`` remains the Seed lifecycle authority. This manifest is the engineering
    request/contract consumed by the Workshop job; it is not a second Seed registry.
    """

    manifest_id: str
    seed_id: str
    source_root: Path
    source_id: str
    source_license: str
    target_profile: str = "python"
    required_components: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("manifest_id", "seed_id", "source_id", "source_license", "target_profile"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ManifestEvidenceError(f"manifest requires a non-empty {field}")
        root = Path(self.source_root)
        if not root.is_dir():
            raise ManifestEvidenceError(f"manifest source root is not a directory: {root}")
        object.__setattr__(self, "source_root", root)
        components = tuple(str(component).strip() for component in self.required_components)
        if any(not component for component in components):
            raise ManifestEvidenceError("manifest required_components must not contain empty ids")
        if len(set(components)) != len(components):
            raise ManifestEvidenceError("manifest required_components must be unique")
        object.__setattr__(self, "required_components", components)

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "seed_id": self.seed_id,
            "source_root": str(self.source_root),
            "source_id": self.source_id,
            "source_license": self.source_license,
            "target_profile": self.target_profile,
            "required_components": list(self.required_components),
        }

    def digest(self) -> str:
        """Return a stable digest for the exact manifest request."""
        encoded = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ManifestRunEvidence:
    """Durable join record between a manifest, a Workshop job, and its event."""

    evidence_id: str
    manifest_id: str
    manifest_digest: str
    seed_id: str
    job_id: str
    event_id: str
    status: str
    target_profile: str
    required_components: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(getattr(self, field), str) and getattr(self, field).strip()
            for field in (
                "evidence_id",
                "manifest_id",
                "manifest_digest",
                "seed_id",
                "job_id",
                "event_id",
                "status",
                "target_profile",
                "created_at",
            )
        ):
            raise ManifestEvidenceError("manifest evidence contains an empty required field")
        object.__setattr__(self, "required_components", tuple(self.required_components))

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "seed_id": self.seed_id,
            "job_id": self.job_id,
            "event_id": self.event_id,
            "status": self.status,
            "target_profile": self.target_profile,
            "required_components": list(self.required_components),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ManifestRunEvidence:
        if not isinstance(raw, dict):
            raise ManifestEvidenceError("manifest evidence must be an object")
        try:
            return cls(
                evidence_id=str(raw["evidence_id"]),
                manifest_id=str(raw["manifest_id"]),
                manifest_digest=str(raw["manifest_digest"]),
                seed_id=str(raw["seed_id"]),
                job_id=str(raw["job_id"]),
                event_id=str(raw["event_id"]),
                status=str(raw["status"]),
                target_profile=str(raw["target_profile"]),
                required_components=tuple(
                    str(value) for value in raw.get("required_components", [])
                ),
                created_at=str(raw["created_at"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestEvidenceError(f"malformed manifest evidence: {exc}") from exc


_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


class FileManifestEvidenceStore:
    """One immutable evidence record per manifest run."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, evidence_id: str) -> Path:
        if not _SAFE_ID.fullmatch(evidence_id):
            raise ManifestEvidenceError(f"unsafe evidence id: {evidence_id!r}")
        return self.root / f"{evidence_id}.json"

    def save(self, evidence: ManifestRunEvidence) -> None:
        path = self._path(evidence.evidence_id)
        if path.exists():
            existing = self.get(evidence.evidence_id)
            if existing != evidence:
                raise ManifestEvidenceError(
                    f"evidence {evidence.evidence_id!r} already exists with different content"
                )
            return
        atomic_write_text(path, json.dumps(evidence.to_dict(), indent=2, sort_keys=True) + "\n")

    def get(self, evidence_id: str) -> ManifestRunEvidence:
        path = self._path(evidence_id)
        if not path.is_file():
            raise ManifestEvidenceError(f"unknown manifest evidence: {evidence_id}")
        try:
            return ManifestRunEvidence.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ManifestEvidenceError(
                f"cannot load manifest evidence {evidence_id}: {exc}"
            ) from exc

    def all_for_seed(self, seed_id: str) -> tuple[ManifestRunEvidence, ...]:
        records = []
        for path in sorted(self.root.glob("*.json")):
            record = self.get(path.stem)
            if record.seed_id == seed_id:
                records.append(record)
        return tuple(records)


@runtime_checkable
class ManifestEvidenceStore(Protocol):
    """Persistence seam for immutable manifest-test evidence."""

    def save(self, evidence: ManifestRunEvidence) -> None: ...

    def get(self, evidence_id: str) -> ManifestRunEvidence: ...

    def all_for_seed(self, seed_id: str) -> tuple[ManifestRunEvidence, ...]: ...


def run_manifest_test(
    manifest: SeedManifest,
    service: CreatorWorkshopService,
    hardware: HardwareRegistry,
    evidence_store: ManifestEvidenceStore,
    *,
    actor_id: str,
    profile: str = "python-version",
    timeout: float = DEFAULT_TIMEOUT,
    cap: int = OUTPUT_CAP,
) -> ManifestRunEvidence:
    """Run a real Workshop test only after all manifest Hardware is active.

    This function deliberately does not install or activate anything. That separation keeps
    discovery, installation, activation, execution, and evidence review independently auditable.
    """
    for component_id in manifest.required_components:
        record = hardware.get(component_id)
        if record is None:
            raise ManifestEvidenceError(f"required Hardware is not registered: {component_id}")
        if record.state != "active":
            raise ManifestEvidenceError(
                f"required Hardware {component_id!r} is {record.state}; "
                "explicit activation is required"
            )

    job: JobRecord = service.run_test(
        manifest.source_root,
        seed_id=manifest.seed_id,
        actor_id=actor_id,
        profile=profile,
        source_id=manifest.source_id,
        source_license=manifest.source_license,
        timeout=timeout,
        cap=cap,
    )
    evidence_id = f"evidence-{manifest.manifest_id}-{job.job_id}"
    event_id = f"evt-{evidence_id}"
    evidence = ManifestRunEvidence(
        evidence_id=evidence_id,
        manifest_id=manifest.manifest_id,
        manifest_digest=manifest.digest(),
        seed_id=manifest.seed_id,
        job_id=job.job_id,
        event_id=event_id,
        status=job.status,
        target_profile=manifest.target_profile,
        required_components=manifest.required_components,
        created_at=job.finished_at,
    )
    evidence_store.save(evidence)
    service.event_publisher(
        EventEnvelope(
            protocol="codeforge.seed",
            version="1.0",
            event_id=event_id,
            seed_id=manifest.seed_id,
            session_id=actor_id,
            event_type="manifest.test.completed",
            timestamp=job.finished_at,
            classification="internal",
            payload={
                "evidence_id": evidence.evidence_id,
                "manifest_id": evidence.manifest_id,
                "manifest_digest": evidence.manifest_digest,
                "job_id": evidence.job_id,
                "status": evidence.status,
                "target_profile": evidence.target_profile,
                "required_components": list(evidence.required_components),
            },
            text_fallback=(
                f"Manifest test {manifest.manifest_id} passed."
                if job.ok
                else f"Manifest test {manifest.manifest_id} did not pass."
            ),
            accessibility_summary=(
                "The manifest test passed and its job evidence was recorded."
                if job.ok
                else "The manifest test failed; inspect the linked job evidence."
            ),
            correlation_id=job.job_id,
        )
    )
    return evidence
