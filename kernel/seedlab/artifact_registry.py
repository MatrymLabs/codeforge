"""Configured persistence for generated-artifact metadata.

The generated files remain at the path recorded by ``ArtifactRecord``. This module governs the
durable metadata/evidence record and preserves legacy JSON records through an explicit dual-read
transition, matching the Seed registry, model store, and run-evidence boundaries.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session as SqlSession

from kernel.seedlab.artifact_store import (
    ArtifactRecord,
    ArtifactStore,
    ArtifactStoreError,
    FileArtifactStore,
)
from kernel.world.db import SeedArtifactRow, open_archive_session


@dataclass
class SqlArtifactStore:
    """Durable artifact metadata store using the platform SQL boundary."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def save(self, record: ArtifactRecord) -> None:
        payload = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        with self.session_factory() as session, session.begin():
            row = session.get(SeedArtifactRow, (record.seed_id, record.artifact_id))
            if row is not None:
                if row.artifact_json != payload:
                    raise ArtifactStoreError(
                        f"artifact {record.artifact_id!r} already exists with different evidence"
                    )
                return
            session.add(
                SeedArtifactRow(
                    seed_id=record.seed_id,
                    artifact_id=record.artifact_id,
                    artifact_json=payload,
                )
            )

    def load(self, seed_id: str, artifact_id: str) -> ArtifactRecord | None:
        with self.session_factory() as session:
            row = session.get(SeedArtifactRow, (seed_id, artifact_id))
        return None if row is None else self._decode(row)

    def all_for_seed(self, seed_id: str) -> list[ArtifactRecord]:
        with self.session_factory() as session:
            rows = (
                session.query(SeedArtifactRow)
                .filter(SeedArtifactRow.seed_id == seed_id)
                .order_by(SeedArtifactRow.artifact_id)
                .all()
            )
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: SeedArtifactRow) -> ArtifactRecord:
        try:
            return ArtifactRecord.from_dict(json.loads(row.artifact_json))
        except (json.JSONDecodeError, TypeError, ValueError, ArtifactStoreError) as exc:
            raise ArtifactStoreError(
                f"corrupt SQL artifact record {row.seed_id}/{row.artifact_id}"
            ) from exc


@dataclass
class DualReadArtifactStore:
    """Read legacy artifact JSON while writing new metadata to SQL."""

    primary: ArtifactStore
    legacy: ArtifactStore

    def save(self, record: ArtifactRecord) -> None:
        self.primary.save(record)

    def load(self, seed_id: str, artifact_id: str) -> ArtifactRecord | None:
        primary = self.primary.load(seed_id, artifact_id)
        legacy = self.legacy.load(seed_id, artifact_id)
        return self._merge(primary, legacy, artifact_id)

    def all_for_seed(self, seed_id: str) -> list[ArtifactRecord]:
        primary = {record.artifact_id: record for record in self.primary.all_for_seed(seed_id)}
        legacy = {record.artifact_id: record for record in self.legacy.all_for_seed(seed_id)}
        return [
            self._merge(primary.get(artifact_id), legacy.get(artifact_id), artifact_id)
            for artifact_id in sorted(primary.keys() | legacy.keys())
        ]

    @staticmethod
    def _merge(
        primary: ArtifactRecord | None,
        legacy: ArtifactRecord | None,
        artifact_id: str,
    ) -> ArtifactRecord:
        if primary is not None and legacy is not None and primary != legacy:
            raise ArtifactStoreError(
                f"artifact {artifact_id!r} differs between SQL and legacy stores"
            )
        record = primary or legacy
        if record is None:
            raise ArtifactStoreError(f"artifact {artifact_id!r} is missing from both stores")
        return record


def artifact_store(backend: str, home: Path) -> ArtifactStore:
    """Build the artifact metadata store selected by the shared SeedLab backend."""
    if backend == "file":
        return FileArtifactStore(Path(home) / "artifacts")
    primary = SqlArtifactStore()
    if backend == "sql":
        return primary
    if backend == "sql-dual-read":
        return DualReadArtifactStore(primary, FileArtifactStore(Path(home) / "artifacts"))
    raise ArtifactStoreError(
        f"unknown artifact store backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def configured_artifact_store(home: Path) -> ArtifactStore:
    """Open artifact metadata through the shared SeedLab registry configuration."""
    backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return artifact_store(backend, home)
