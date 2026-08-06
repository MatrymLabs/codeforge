"""The CF-103 connector lifecycle remains durable and auditable across restart."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kernel.seedlab.audit_registry import FileAuditStore
from kernel.seedlab.connector_registry import (
    ConnectorRegistryError,
    FileConnectorRegistry,
    SqlConnectorRegistry,
)
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import SourceRecord, local_connector_manifest
from kernel.world.db import ArchiveBase


def _source(source_id: str = "demo-source") -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        provenance=Provenance(source_id, owner="alice", license="MIT", visibility="private"),
        root="/authorized/demo-source",
        file_count=2,
        branch="main",
        commit="abc123",
        digest="sha256:source",
    )


def _registry(tmp_path: Path, clock: str = "2026-08-05T00:00:00Z") -> FileConnectorRegistry:
    return FileConnectorRegistry(
        tmp_path / "connectors",
        audit=FileAuditStore(tmp_path / "audit.jsonl"),
        clock=lambda: clock,
    )


def test_registration_survives_restart_and_is_idempotent(tmp_path: Path) -> None:
    source = _source()
    manifest = local_connector_manifest("seed-demo", pinned_digest=source.digest)
    first = _registry(tmp_path).register(
        "seed-demo", source, manifest, actor="alice", correlation_id="trace-1"
    )

    recovered = _registry(tmp_path).load("seed-demo", source.source_id)
    assert recovered == first
    assert _registry(tmp_path).register("seed-demo", source, manifest, actor="alice") == first
    assert len(_registry(tmp_path).audit.all_records()) == 1  # type: ignore[union-attr]


def test_registration_conflict_fails_closed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    source = _source()
    registry.register("seed-demo", source, local_connector_manifest("seed-demo"), actor="alice")
    with pytest.raises(ConnectorRegistryError, match="different evidence"):
        registry.register(
            "seed-demo",
            replace(source, digest="sha256:changed"),
            local_connector_manifest("seed-demo", pinned_digest="sha256:changed"),
            actor="alice",
        )


def test_remove_keeps_tombstone_and_audit_history(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    source = _source()
    registry.register("seed-demo", source, local_connector_manifest("seed-demo"), actor="alice")

    removed = registry.remove(
        "seed-demo",
        source.source_id,
        actor="alice",
        reason="source retired",
        correlation_id="trace-2",
    )
    recovered = FileConnectorRegistry(
        tmp_path / "connectors", audit=FileAuditStore(tmp_path / "audit.jsonl")
    )
    assert removed.state == "removed"
    assert recovered.load("seed-demo", source.source_id).state == "removed"  # type: ignore[union-attr]
    assert recovered.active_for_seed("seed-demo") == []
    assert [entry["action"] for entry in recovered.audit.all_records()] == [  # type: ignore[union-attr]
        "connector.registered",
        "connector.removed",
    ]


def test_failure_is_durable_and_visible(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    source = _source()
    registry.register("seed-demo", source, local_connector_manifest("seed-demo"), actor="alice")
    failed = registry.record_failure(
        "seed-demo", source.source_id, actor="system", failure="model extraction failed"
    )

    recovered = _registry(tmp_path).load("seed-demo", source.source_id)
    assert recovered == failed
    assert recovered.state == "failed"  # type: ignore[union-attr]
    assert recovered.failure == "model extraction failed"  # type: ignore[union-attr]
    assert _registry(tmp_path).active_for_seed("seed-demo") == []


def test_revocation_is_a_durable_non_active_state(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    source = _source()
    registry.register("seed-demo", source, local_connector_manifest("seed-demo"), actor="alice")
    revoked = registry.revoke("seed-demo", source.source_id, actor="operator", reason="policy")
    assert revoked.state == "revoked"
    assert registry.active_for_seed("seed-demo") == []


def test_sql_registration_survives_restart_and_updates_the_same_row(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    audit = FileAuditStore(tmp_path / "audit.jsonl")
    registry = SqlConnectorRegistry(
        tmp_path / "unused-connectors",
        audit=audit,
        session_factory=lambda: Session(engine),
    )
    source = _source()
    registry.register("seed-demo", source, local_connector_manifest("seed-demo"), actor="alice")
    registry.remove("seed-demo", source.source_id, actor="alice", reason="retired")

    recovered = SqlConnectorRegistry(
        tmp_path / "unused-connectors",
        audit=FileAuditStore(tmp_path / "audit.jsonl"),
        session_factory=lambda: Session(engine),
    )
    registration = recovered.load("seed-demo", source.source_id)
    assert registration is not None and registration.state == "removed"
    assert recovered.active_for_seed("seed-demo") == []
