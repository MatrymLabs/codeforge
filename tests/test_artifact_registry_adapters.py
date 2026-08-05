"""Configured artifact metadata storage is shared by API and workspace projections."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from adapters.api import _seedlab_artifact_store, _seedlab_kernel
from kernel.seedlab.artifact_registry import DualReadArtifactStore, SqlArtifactStore
from kernel.seedlab.artifact_store import ArtifactRecord, ArtifactStoreError, FileArtifactStore
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.workspace_contract import build_workspace_contract
from kernel.world.db import ArchiveBase


def _record(seed_id: str = "seed-1", artifact_id: str = "artifact-1") -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        seed_id=seed_id,
        name="target",
        kind="cli",
        path="/workspace/target",
        files=("app.py",),
        checksums={"app.py": "sha256:app"},
        manifest_hash="sha256:manifest",
        provenance=Provenance("source-1", owner="alice", license="MIT"),
        model_identity="TaskModel",
        run_profiles=("pytest",),
    )


def test_sql_artifact_store_survives_restart_and_rejects_overwrite(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    record = _record()
    store = SqlArtifactStore(lambda: Session(engine))

    store.save(record)
    store.save(record)
    assert SqlArtifactStore(lambda: Session(engine)).load(record.seed_id, record.artifact_id) == record
    with pytest.raises(ArtifactStoreError, match="different evidence"):
        store.save(replace(record, model_identity="tampered"))


def test_dual_read_artifact_store_reads_legacy_and_rejects_conflicts(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    home = tmp_path / ".seedlab"
    record = _record()
    legacy = FileArtifactStore(home / "artifacts")
    legacy.save(record)
    store = DualReadArtifactStore(SqlArtifactStore(lambda: Session(engine)), legacy)

    assert store.load(record.seed_id, record.artifact_id) == record
    conflicting = replace(record, model_identity="tampered")
    SqlArtifactStore(lambda: Session(engine)).save(conflicting)
    with pytest.raises(ArtifactStoreError, match="differs between SQL and legacy"):
        store.load(record.seed_id, record.artifact_id)


def test_api_and_workspace_contract_share_sql_artifact_metadata(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    _seedlab_kernel().create_seed("SQL Artifacts", "alice", "artifact authority", seed_id="seed-sql-artifacts")
    record = _record("seed-sql-artifacts")
    _seedlab_artifact_store().save(record)

    contract = build_workspace_contract("seed-sql-artifacts", root=home)

    assert contract.project_state["targets"]
    assert "target" in contract.project_state["targets"][0]
    assert not list((home / "artifacts").glob("**/*.json"))


def test_workspace_contract_dual_reads_legacy_artifacts(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql-dual-read")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Legacy Artifacts", "alice", "compatibility", seed_id="seed-legacy-artifacts"
    )
    FileArtifactStore(home / "artifacts").save(_record("seed-legacy-artifacts"))

    contract = build_workspace_contract("seed-legacy-artifacts", root=home)

    assert "target" in contract.project_state["targets"][0]
