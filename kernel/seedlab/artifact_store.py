"""Persist generated target artifacts for a Seed.

The CLI generator already creates a real target and proves it runs. This module records that output
as Seed state: what was generated, which source/model it came from, which validation runs support
it, and how many bytes/files were produced. A fresh store over the same directory recovers the same
records, so generated target evidence survives a restart.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from kernel.seedlab.cli_generator import GeneratedArtifact
from kernel.seedlab.project_model import Provenance, SeedLabError
from kernel.seedlab.tool_runner import ToolRunResult
from kernel.shelf.atomic_write import atomic_write_text

_SCHEMA = 1
_SLUG = re.compile(r"[^a-z0-9]+")
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


class ArtifactStoreError(Exception):
    """An artifact record is malformed, corrupt, or unsafe to persist."""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _safe_segment(value: str) -> str:
    return _UNSAFE.sub("_", value)


def artifact_id_for(seed_id: str, artifact: GeneratedArtifact) -> str:
    """A stable, filesystem-safe id for one generated artifact under one Seed."""
    slug = _SLUG.sub("-", artifact.name.strip().lower()).strip("-") or "artifact"
    digest = artifact.manifest_hash.removeprefix("sha256:") or "unknown"
    prefix = _SLUG.sub("-", seed_id.strip().lower()).strip("-") or "seed"
    # Keep the complete content digest in the identity. A short display prefix is useful in
    # labels, but truncating the persisted ID would let two distinct immutable artifacts alias.
    return f"artifact-{prefix}-{slug}-{digest}"


@dataclass(frozen=True)
class ArtifactRecord:
    """Durable record of one generated target artifact."""

    artifact_id: str
    seed_id: str
    name: str
    kind: str
    path: str
    files: tuple[str, ...]
    checksums: dict[str, str]
    manifest_hash: str
    provenance: Provenance
    model_identity: str
    run_profiles: tuple[str, ...] = ()
    bytes: int = 0
    created_at: str = ""
    correlation_id: str = ""
    job_ids: tuple[str, ...] = ()
    dependency_lock_digest: str = ""
    sbom: dict[str, object] = field(default_factory=dict)
    sbom_status: str = "not_recorded"
    reproduction_instructions: str = ""
    file_ownership: dict[str, str] = field(default_factory=dict)
    generator_id: str = "codeforge.cli-generator"
    generator_version: str = "1"
    reproducibility_status: str = "not_evaluated"
    input_digest: str = ""
    transformation_id: str = ""
    transformation_version: str = ""
    output_model_digest: str = ""

    def __post_init__(self) -> None:
        for field_name in ("artifact_id", "seed_id", "name", "kind", "manifest_hash"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ArtifactStoreError(f"artifact record needs a non-empty {field_name}")
        if self.bytes < 0:
            raise ArtifactStoreError("artifact bytes cannot be negative")
        object.__setattr__(self, "files", tuple(self.files))
        object.__setattr__(self, "run_profiles", tuple(self.run_profiles))
        object.__setattr__(self, "job_ids", tuple(self.job_ids))
        object.__setattr__(self, "sbom", dict(self.sbom))
        object.__setattr__(self, "file_ownership", dict(self.file_ownership))
        if self.sbom_status not in {"not_recorded", "recorded", "not_applicable"}:
            raise ArtifactStoreError(f"unknown SBOM status: {self.sbom_status!r}")
        if self.reproducibility_status not in {"not_evaluated", "reproducible", "different"}:
            raise ArtifactStoreError(
                f"unknown reproducibility status: {self.reproducibility_status!r}"
            )

    @property
    def deployment_eligible(self) -> bool:
        """Whether the registry has enough evidence for a governed deployment request."""
        return bool(
            self.files
            and self.checksums
            and self.provenance.source_id.strip()
            and self.provenance.license.strip()
            and self.run_profiles
            and self.dependency_lock_digest.strip()
            and self.sbom_status in {"recorded", "not_applicable"}
            and self.reproduction_instructions.strip()
            and all(
                self.file_ownership.get(path) in {"generated", "scaffold", "managed_region"}
                for path in self.files
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "artifact_id": self.artifact_id,
            "seed_id": self.seed_id,
            "name": self.name,
            "kind": self.kind,
            "path": self.path,
            "files": list(self.files),
            "checksums": dict(self.checksums),
            "manifest_hash": self.manifest_hash,
            "provenance": {
                "source_id": self.provenance.source_id,
                "owner": self.provenance.owner,
                "license": self.provenance.license,
                "visibility": self.provenance.visibility,
                "allowed_use": self.provenance.allowed_use,
            },
            "model_identity": self.model_identity,
            "run_profiles": list(self.run_profiles),
            "bytes": self.bytes,
            "created_at": self.created_at,
            "correlation_id": self.correlation_id,
            "job_ids": list(self.job_ids),
            "dependency_lock_digest": self.dependency_lock_digest,
            "sbom": dict(self.sbom),
            "sbom_status": self.sbom_status,
            "reproduction_instructions": self.reproduction_instructions,
            "file_ownership": dict(self.file_ownership),
            "generator_id": self.generator_id,
            "generator_version": self.generator_version,
            "reproducibility_status": self.reproducibility_status,
            "input_digest": self.input_digest,
            "transformation_id": self.transformation_id,
            "transformation_version": self.transformation_version,
            "output_model_digest": self.output_model_digest,
        }

    @classmethod
    def from_dict(cls, data: object) -> ArtifactRecord:
        if not isinstance(data, dict):
            raise ArtifactStoreError("artifact record must be an object")
        try:
            if int(data.get("schema", _SCHEMA)) != _SCHEMA:
                raise ArtifactStoreError(f"unsupported artifact schema {data.get('schema')!r}")
            return cls(
                artifact_id=str(data["artifact_id"]),
                seed_id=str(data["seed_id"]),
                name=str(data["name"]),
                kind=str(data["kind"]),
                path=str(data.get("path", "")),
                files=tuple(str(item) for item in data.get("files", [])),
                checksums={str(k): str(v) for k, v in dict(data.get("checksums", {})).items()},
                manifest_hash=str(data["manifest_hash"]),
                provenance=Provenance(**dict(data["provenance"])),
                model_identity=str(data.get("model_identity", "")),
                run_profiles=tuple(str(item) for item in data.get("run_profiles", [])),
                bytes=int(data.get("bytes", 0)),
                created_at=str(data.get("created_at", "")),
                correlation_id=str(data.get("correlation_id", "")),
                job_ids=tuple(str(item) for item in data.get("job_ids", [])),
                dependency_lock_digest=str(data.get("dependency_lock_digest", "")),
                sbom=dict(data.get("sbom", {})),
                sbom_status=str(data.get("sbom_status", "not_recorded")),
                reproduction_instructions=str(data.get("reproduction_instructions", "")),
                file_ownership={
                    str(key): str(value)
                    for key, value in dict(data.get("file_ownership", {})).items()
                },
                generator_id=str(data.get("generator_id", "codeforge.cli-generator")),
                generator_version=str(data.get("generator_version", "1")),
                reproducibility_status=str(data.get("reproducibility_status", "not_evaluated")),
                input_digest=str(data.get("input_digest", "")),
                transformation_id=str(data.get("transformation_id", "")),
                transformation_version=str(data.get("transformation_version", "")),
                output_model_digest=str(data.get("output_model_digest", "")),
            )
        except (KeyError, TypeError, ValueError, SeedLabError) as exc:
            raise ArtifactStoreError(f"malformed artifact record: {exc}") from exc


@runtime_checkable
class ArtifactStore(Protocol):
    """Persistence boundary for generated artifact records."""

    def save(self, record: ArtifactRecord) -> None: ...

    def load(self, seed_id: str, artifact_id: str) -> ArtifactRecord | None: ...

    def all_for_seed(self, seed_id: str) -> list[ArtifactRecord]: ...


@dataclass
class InMemoryArtifactStore:
    """Volatile artifact records for tests and ephemeral proof runs."""

    _records: dict[tuple[str, str], ArtifactRecord] = field(default_factory=dict)

    def save(self, record: ArtifactRecord) -> None:
        existing = self._records.get((record.seed_id, record.artifact_id))
        if existing is not None and existing != record:
            raise ArtifactStoreError(
                f"artifact {record.artifact_id!r} already exists with different evidence"
            )
        self._records[(record.seed_id, record.artifact_id)] = record

    def load(self, seed_id: str, artifact_id: str) -> ArtifactRecord | None:
        return self._records.get((seed_id, artifact_id))

    def all_for_seed(self, seed_id: str) -> list[ArtifactRecord]:
        return [record for (sid, _), record in sorted(self._records.items()) if sid == seed_id]


@dataclass
class FileArtifactStore:
    """Durable artifact store: one JSON file per artifact under ``<root>/<seed_id>/``."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, seed_id: str) -> Path:
        path = self.root / _safe_segment(seed_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, record: ArtifactRecord) -> None:
        target = self._dir(record.seed_id) / f"{_safe_segment(record.artifact_id)}.json"
        existing = self.load(record.seed_id, record.artifact_id)
        if existing is not None and existing != record:
            raise ArtifactStoreError(
                f"artifact {record.artifact_id!r} already exists with different evidence"
            )
        if existing is None:
            atomic_write_text(target, json.dumps(record.to_dict(), indent=2))

    def load(self, seed_id: str, artifact_id: str) -> ArtifactRecord | None:
        path = self.root / _safe_segment(seed_id) / f"{_safe_segment(artifact_id)}.json"
        if not path.is_file():
            return None
        try:
            return ArtifactRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise ArtifactStoreError(f"corrupt artifact record {path}: {exc}") from exc

    def all_for_seed(self, seed_id: str) -> list[ArtifactRecord]:
        seed_dir = self.root / _safe_segment(seed_id)
        if not seed_dir.is_dir():
            return []
        records: list[ArtifactRecord] = []
        for path in sorted(seed_dir.glob("*.json")):
            record = self.load(seed_id, path.stem)
            if record is not None:
                records.append(record)
        return records


def record_generated_artifact(
    seed_id: str,
    artifact: GeneratedArtifact,
    *,
    runs: Sequence[ToolRunResult] = (),
    kind: str = "cli",
    clock: object = _utcnow,
    correlation_id: str = "",
    job_ids: Sequence[str] = (),
    dependency_lock_digest: str = "",
    sbom: dict[str, object] | None = None,
    sbom_status: str = "not_recorded",
    reproduction_instructions: str = "",
    file_ownership: dict[str, str] | None = None,
    generator_id: str = "codeforge.cli-generator",
    generator_version: str = "1",
) -> ArtifactRecord:
    """Convert a generated artifact into a persisted Seed artifact record."""
    when = clock() if callable(clock) else _utcnow()
    return ArtifactRecord(
        artifact_id=artifact_id_for(seed_id, artifact),
        seed_id=seed_id,
        name=artifact.name,
        kind=kind,
        path=artifact.dest,
        files=tuple(artifact.files),
        checksums=dict(artifact.checksums),
        manifest_hash=artifact.manifest_hash,
        provenance=artifact.provenance,
        model_identity=artifact.model_identity,
        run_profiles=tuple(run.profile or run.kind for run in runs),
        bytes=_artifact_bytes(artifact),
        created_at=str(when),
        correlation_id=correlation_id.strip(),
        job_ids=tuple(job_ids),
        dependency_lock_digest=dependency_lock_digest.strip(),
        sbom=dict(sbom or {}),
        sbom_status=sbom_status,
        reproduction_instructions=reproduction_instructions.strip(),
        file_ownership=dict(file_ownership or {}),
        generator_id=generator_id.strip(),
        generator_version=generator_version.strip(),
        input_digest=artifact.input_digest,
        transformation_id=artifact.transformation_id,
        transformation_version=artifact.transformation_version,
        output_model_digest=artifact.output_model_digest,
    )


def _artifact_bytes(artifact: GeneratedArtifact) -> int:
    root = Path(artifact.dest).resolve()
    total = 0
    for rel in artifact.files:
        if Path(rel).is_absolute():
            raise ArtifactStoreError(f"artifact file path must be relative: {rel!r}")
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ArtifactStoreError(f"artifact file path escapes its root: {rel!r}") from exc
        if not path.is_file():
            raise ArtifactStoreError(f"artifact file is missing: {rel!r}")
        total += path.stat().st_size
    return total


def compare_artifact_reproduction(
    original: ArtifactRecord, rerun: ArtifactRecord
) -> dict[str, object]:
    """Compare two exact artifact records without silently treating a rerun as identical."""
    same_inputs = (
        original.seed_id == rerun.seed_id
        and original.model_identity == rerun.model_identity
        and original.provenance == rerun.provenance
        and original.generator_id == rerun.generator_id
        and original.generator_version == rerun.generator_version
        and original.input_digest == rerun.input_digest
        and original.transformation_id == rerun.transformation_id
        and original.transformation_version == rerun.transformation_version
    )
    same_output = (
        original.manifest_hash == rerun.manifest_hash and original.checksums == rerun.checksums
    )
    return {
        "original_artifact_id": original.artifact_id,
        "rerun_artifact_id": rerun.artifact_id,
        "same_inputs": same_inputs,
        "same_output": same_output,
        "reproducible": same_inputs and same_output,
        "original_manifest_hash": original.manifest_hash,
        "rerun_manifest_hash": rerun.manifest_hash,
    }


def artifact_label(record: ArtifactRecord) -> str:
    """The Project Hub target label for one generated artifact."""
    return (
        f"{record.name} ({record.kind}, {len(record.files)} files, {record.bytes} bytes, "
        f"manifest {record.manifest_hash[:12]}) <- {record.provenance.source_id}"
    )


def artifact_labels(store: ArtifactStore, seed_id: str) -> tuple[str, ...]:
    """All generated target labels for a Seed."""
    return tuple(artifact_label(record) for record in store.all_for_seed(seed_id))


def build_report_artifacts(records: Sequence[ArtifactRecord]) -> list[dict[str, object]]:
    """Project artifact records into the Master Client's Build.Report artifact entries."""
    return [
        {
            "artifact_id": record.artifact_id,
            "name": record.name,
            "kind": record.kind,
            "bytes": record.bytes,
            "path": record.path,
            "manifest_hash": record.manifest_hash,
            "source_id": record.provenance.source_id,
            "model_identity": record.model_identity,
            "run_profiles": list(record.run_profiles),
            "job_ids": list(record.job_ids),
            "sbom_status": record.sbom_status,
            "deployment_eligible": record.deployment_eligible,
            "reproducibility_status": record.reproducibility_status,
            "input_digest": record.input_digest,
            "transformation_id": record.transformation_id,
            "transformation_version": record.transformation_version,
            "output_model_digest": record.output_model_digest,
        }
        for record in records
    ]
