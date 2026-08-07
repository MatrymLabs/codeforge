"""Durable audit and source-provenance records share the platform persistence boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from adapters.api import _seedlab_kernel
from kernel.seedlab.audit_registry import (
    DualReadAuditStore,
    FileAuditStore,
    SqlAuditStore,
)
from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel
from kernel.seedlab.model_store import InMemorySeedModels
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.provenance_registry import (
    DualReadProvenanceStore,
    FileProvenanceStore,
    ProvenanceStoreError,
    SqlProvenanceStore,
    configured_provenance_store,
)
from kernel.seedlab.source_connector import SourceRecord
from kernel.seedlab.workspace_contract import build_workspace_contract
from kernel.seedlab.workspace_verb import workspace_command
from kernel.world import audit
from kernel.world.db import ArchiveBase, AuditEventRow


def _source(source_id: str = "source-1") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        provenance=Provenance(
            source_id,
            owner="alice",
            license="MIT",
            visibility="private",
            allowed_use="platform tests",
        ),
        root="/workspace/source",
        file_count=3,
        branch="main",
        commit="abc123",
    )


def test_sql_provenance_survives_restart_and_rejects_conflict(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    record = _source()
    store = SqlProvenanceStore(lambda: Session(engine))

    store.save("seed-1", record)
    store.save("seed-1", record)
    assert SqlProvenanceStore(lambda: Session(engine)).load("seed-1", record.source_id) == record
    with pytest.raises(ProvenanceStoreError, match="different provenance"):
        store.save("seed-1", replace(record, commit="changed"))


def test_dual_read_provenance_reads_legacy_and_rejects_conflict(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    record = _source()
    legacy = FileProvenanceStore(tmp_path / "sources")
    legacy.save("seed-1", record)
    store = DualReadProvenanceStore(SqlProvenanceStore(lambda: Session(engine)), legacy)

    assert store.load("seed-1", record.source_id) == record
    SqlProvenanceStore(lambda: Session(engine)).save("seed-1", replace(record, commit="changed"))
    with pytest.raises(ProvenanceStoreError, match="differs between SQL and legacy"):
        store.load("seed-1", record.source_id)


def test_workspace_contract_recovers_sql_source_provenance(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    _seedlab_kernel().create_seed(
        "SQL Sources", "alice", "source authority", seed_id="seed-sql-source"
    )
    record = _source("project-source")
    configured_provenance_store(home).save("seed-sql-source", record)

    contract = build_workspace_contract("seed-sql-source", root=home)

    assert contract.project_state["sources"]
    connection = next(
        package for package in contract.packages if package.package == "Source.Connection"
    )
    assert connection.payload["source_id"] == record.source_id
    assert connection.payload["license"] == "MIT"
    assert not list((home / "sources").glob("**/*.json"))


def test_workspace_connect_persists_source_provenance(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    source_root = tmp_path / "project"
    source_root.mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='project'\n", encoding="utf-8")
    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: "2026-08-05T00:00:00+00:00")
    record = kernel.create_seed("Project", "owner", "source proof", seed_id="seed-source")

    out = workspace_command(
        type("Session", (), {"player_id": "owner", "rank": "owner"})(),
        f"connect {record.identity.seed_id} {source_root}",
        kernel=kernel,
        model_store=InMemorySeedModels(),
        provenance_store=FileProvenanceStore(home / "sources"),
    )

    assert "Connected" in out
    sources = FileProvenanceStore(home / "sources").all_for_seed(record.identity.seed_id)
    assert len(sources) == 1 and sources[0].provenance.owner == "owner"


def test_dual_read_audit_preserves_legacy_and_appends_sql(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    legacy = FileAuditStore(tmp_path / "audit.jsonl")
    legacy.append({"ts": "1", "actor": "alice", "action": "connect", "detail": "legacy"})
    store = DualReadAuditStore(SqlAuditStore(lambda: Session(engine)), legacy)

    store.append({"ts": "2", "actor": "alice", "action": "model", "detail": "sql"})

    records = store.all_records()
    assert {record["detail"] for record in records} == {"legacy", "sql"}
    assert store.verify() is True


def test_sql_audit_chain_detects_tampering_and_world_audit_routes_to_sql(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CODEFORGE_AUDIT_BACKEND", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "platform.db"))

    audit.record("alice", "connect", "source", ts="2026-08-05T00:00:00Z")
    assert audit.tail()[-1]["action"] == "connect"
    assert audit.verify() is True

    with audit_store_session() as session:
        row = session.get(AuditEventRow, 0)
        assert row is not None
        row.payload_json = (
            '{"action":"forged","actor":"alice","detail":"source","ts":"2026-08-05T00:00:00Z"}'
        )
        session.commit()
    assert audit.verify() is False


def audit_store_session():
    """Open the configured database without reaching through the audit module's store seam."""
    from kernel.world.db import open_archive_session

    return open_archive_session()
