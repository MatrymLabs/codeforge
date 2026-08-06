"""Configured persistence for immutable manifest-test evidence."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session as SqlSession

from kernel.platform_db import SeedManifestEvidenceRow, open_archive_session
from kernel.seedlab.manifest_evidence import (
    FileManifestEvidenceStore,
    ManifestEvidenceError,
    ManifestEvidenceStore,
    ManifestRunEvidence,
)


@dataclass
class SqlManifestEvidenceStore:
    """Durable manifest evidence using the platform SQL boundary."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def save(self, evidence: ManifestRunEvidence) -> None:
        payload = json.dumps(evidence.to_dict(), sort_keys=True, separators=(",", ":"))
        with self.session_factory() as session, session.begin():
            row = session.get(SeedManifestEvidenceRow, (evidence.seed_id, evidence.evidence_id))
            if row is not None:
                if row.evidence_json != payload:
                    raise ManifestEvidenceError(
                        f"evidence {evidence.evidence_id!r} already exists with different content"
                    )
                return
            session.add(
                SeedManifestEvidenceRow(
                    seed_id=evidence.seed_id,
                    evidence_id=evidence.evidence_id,
                    evidence_json=payload,
                )
            )

    def get(self, evidence_id: str) -> ManifestRunEvidence:
        with self.session_factory() as session:
            row = (
                session.query(SeedManifestEvidenceRow)
                .filter(SeedManifestEvidenceRow.evidence_id == evidence_id)
                .first()
            )
        if row is None:
            raise ManifestEvidenceError(f"unknown manifest evidence: {evidence_id}")
        try:
            return ManifestRunEvidence.from_dict(json.loads(row.evidence_json))
        except (json.JSONDecodeError, TypeError, ValueError, ManifestEvidenceError) as exc:
            raise ManifestEvidenceError(f"cannot load SQL manifest evidence {evidence_id}") from exc

    def all_for_seed(self, seed_id: str) -> tuple[ManifestRunEvidence, ...]:
        with self.session_factory() as session:
            rows = (
                session.query(SeedManifestEvidenceRow)
                .filter(SeedManifestEvidenceRow.seed_id == seed_id)
                .order_by(SeedManifestEvidenceRow.evidence_id)
                .all()
            )
        return tuple(self._decode(row) for row in rows)

    @staticmethod
    def _decode(row: SeedManifestEvidenceRow) -> ManifestRunEvidence:
        try:
            return ManifestRunEvidence.from_dict(json.loads(row.evidence_json))
        except (json.JSONDecodeError, TypeError, ValueError, ManifestEvidenceError) as exc:
            raise ManifestEvidenceError(
                f"cannot load SQL manifest evidence {row.evidence_id}"
            ) from exc


@dataclass
class DualReadManifestEvidenceStore:
    """Read legacy evidence JSON while writing new evidence to SQL."""

    primary: ManifestEvidenceStore
    legacy: ManifestEvidenceStore

    def save(self, evidence: ManifestRunEvidence) -> None:
        self.primary.save(evidence)

    def get(self, evidence_id: str) -> ManifestRunEvidence:
        primary = self._try_get(self.primary, evidence_id)
        legacy = self._try_get(self.legacy, evidence_id)
        return self._merge(primary, legacy, evidence_id)

    def all_for_seed(self, seed_id: str) -> tuple[ManifestRunEvidence, ...]:
        primary = {item.evidence_id: item for item in self.primary.all_for_seed(seed_id)}
        legacy = {item.evidence_id: item for item in self.legacy.all_for_seed(seed_id)}
        return tuple(
            self._merge(primary.get(evidence_id), legacy.get(evidence_id), evidence_id)
            for evidence_id in sorted(primary.keys() | legacy.keys())
        )

    @staticmethod
    def _try_get(
        store: ManifestEvidenceStore, evidence_id: str
    ) -> ManifestRunEvidence | None:
        try:
            return store.get(evidence_id)
        except ManifestEvidenceError as exc:
            if str(exc) == f"unknown manifest evidence: {evidence_id}":
                return None
            raise

    @staticmethod
    def _merge(
        primary: ManifestRunEvidence | None,
        legacy: ManifestRunEvidence | None,
        evidence_id: str,
    ) -> ManifestRunEvidence:
        if primary is not None and legacy is not None and primary != legacy:
            raise ManifestEvidenceError(
                f"evidence {evidence_id!r} differs between SQL and legacy stores"
            )
        record = primary or legacy
        if record is None:
            raise ManifestEvidenceError(f"unknown manifest evidence: {evidence_id}")
        return record


def manifest_evidence_store(backend: str, home: Path) -> ManifestEvidenceStore:
    """Build the manifest-evidence store selected by the shared SeedLab backend."""
    if backend == "file":
        return FileManifestEvidenceStore(Path(home) / "evidence")
    primary = SqlManifestEvidenceStore()
    if backend == "sql":
        return primary
    if backend == "sql-dual-read":
        return DualReadManifestEvidenceStore(
            primary, FileManifestEvidenceStore(Path(home) / "evidence")
        )
    raise ManifestEvidenceError(
        f"unknown manifest evidence backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def configured_manifest_evidence_store(home: Path) -> ManifestEvidenceStore:
    """Open manifest evidence through the shared SeedLab registry configuration."""
    backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return manifest_evidence_store(backend, home)
