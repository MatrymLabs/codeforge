"""Configured manifest evidence storage is shared by SQL and workspace projections."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from adapters.api import _seedlab_kernel
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.manifest_evidence import (
    FileManifestEvidenceStore,
    ManifestEvidenceError,
    ManifestRunEvidence,
)
from kernel.seedlab.manifest_registry import (
    DualReadManifestEvidenceStore,
    SqlManifestEvidenceStore,
    configured_manifest_evidence_store,
)
from kernel.seedlab.workspace_contract import build_workspace_contract
from kernel.world.db import ArchiveBase


def _evidence(seed_id: str = "seed-1", evidence_id: str = "evidence-1") -> ManifestRunEvidence:
    return ManifestRunEvidence(
        evidence_id=evidence_id,
        manifest_id="manifest-1",
        manifest_digest="digest-1",
        seed_id=seed_id,
        job_id="job-1",
        event_id="evt-1",
        status="succeeded",
        target_profile="python",
        required_components=("event-ledger",),
        created_at="2026-08-05T00:00:00+00:00",
    )


def test_sql_manifest_evidence_survives_restart_and_rejects_conflict(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    evidence = _evidence()
    store = SqlManifestEvidenceStore(lambda: Session(engine))

    store.save(evidence)
    store.save(evidence)
    assert SqlManifestEvidenceStore(lambda: Session(engine)).get(evidence.evidence_id) == evidence
    with pytest.raises(ManifestEvidenceError, match="different content"):
        store.save(replace(evidence, status="failed"))


def test_dual_read_manifest_evidence_reads_legacy_and_rejects_conflict(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    home = tmp_path / ".seedlab"
    evidence = _evidence()
    legacy = FileManifestEvidenceStore(home / "evidence")
    legacy.save(evidence)
    store = DualReadManifestEvidenceStore(SqlManifestEvidenceStore(lambda: Session(engine)), legacy)

    assert store.get(evidence.evidence_id) == evidence
    SqlManifestEvidenceStore(lambda: Session(engine)).save(replace(evidence, status="failed"))
    with pytest.raises(ManifestEvidenceError, match="differs between SQL and legacy"):
        store.get(evidence.evidence_id)


def test_workspace_contract_loads_configured_sql_manifest_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    _seedlab_kernel().create_seed("SQL Evidence", "alice", "manifest authority", seed_id="seed-sql-evidence")
    evidence = _evidence("seed-sql-evidence")
    configured_manifest_evidence_store(home).save(evidence)

    contract = build_workspace_contract("seed-sql-evidence", root=home)

    manifest_package = next(
        package for package in contract.packages if package.package == "Engineering.Evidence"
    )
    assert manifest_package.payload["manifest_runs"][0]["evidence_id"] == evidence.evidence_id
    assert not list((home / "evidence").glob("*.json"))


def test_workspace_contract_dual_reads_legacy_manifest_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql-dual-read")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Legacy Evidence", "alice", "compatibility", seed_id="seed-legacy-evidence"
    )
    FileManifestEvidenceStore(home / "evidence").save(_evidence("seed-legacy-evidence"))

    contract = build_workspace_contract("seed-legacy-evidence", root=home)

    manifest_package = next(
        package for package in contract.packages if package.package == "Engineering.Evidence"
    )
    assert manifest_package.payload["manifest_runs"][0]["evidence_id"] == "evidence-1"
