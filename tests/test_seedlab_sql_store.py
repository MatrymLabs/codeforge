"""Contract tests for the SQL-backed generic Seed registry store."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.registry import (
    DualReadSeedStore,
    SeedRegistryConflict,
    migrate_file_registry,
)
from kernel.seedlab.sql_store import SqlSeedStore
from kernel.world.db import ArchiveBase


def _store(path: Path) -> SqlSeedStore:
    engine = create_engine(f"sqlite:///{path}")
    ArchiveBase.metadata.create_all(engine)
    return SqlSeedStore(lambda: Session(engine))


def test_sql_seed_store_round_trip_survives_new_kernel(tmp_path: Path) -> None:
    store = _store(tmp_path / "platform.db")
    kernel = SeedKernel(store, clock=lambda: "2026-08-05T00:00:00Z")
    created = kernel.create_seed(
        "Engineering Seed",
        "alice",
        "build a service",
        seed_id="seed-engineering",
        product_type="service",
        domain_modules=("api", "testing"),
    )
    running = kernel.start(created.identity.seed_id, "alice")

    recovered = SeedKernel(_store(tmp_path / "platform.db"))
    actual = recovered.get("seed-engineering")

    assert actual == running
    assert [record.identity.seed_id for record in recovered.list_seeds()] == [
        "seed-engineering"
    ]
    assert actual.identity.domain_modules == ("api", "testing")
    assert [event.action for event in actual.audit] == ["created", "started"]


def test_sql_seed_store_replaces_one_identity_without_duplicates(tmp_path: Path) -> None:
    store = _store(tmp_path / "platform.db")
    kernel = SeedKernel(store, id_minter=lambda _name: "seed-fixed")
    first = kernel.create_seed("One", "alice", "first")
    second = kernel.get(first.identity.seed_id)

    assert second == first
    assert len(kernel.list_seeds()) == 1


def test_file_registry_import_is_restartable_and_dual_read_is_safe(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    legacy = FileSeedStore(home / "seeds")
    source = SeedKernel(legacy, clock=lambda: "2026-08-05T00:00:00Z")
    source.create_seed("Legacy", "alice", "migration", seed_id="seed-legacy")
    sql = _store(tmp_path / "platform.db")

    result = migrate_file_registry(home, target=sql)
    assert result.imported == 1 and result.already_present == 0
    assert migrate_file_registry(home, target=sql).imported == 0

    dual = SeedKernel(DualReadSeedStore(sql, legacy))
    assert dual.get("seed-legacy").identity.name == "Legacy"
    updated = dual.start("seed-legacy", "alice")
    assert sql.load("seed-legacy") == updated


def test_file_registry_import_rejects_conflicts_before_writing(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    legacy = FileSeedStore(home / "seeds")
    source = SeedKernel(legacy, id_minter=lambda _name: "seed-conflict")
    source.create_seed("Legacy", "alice", "old")
    sql = _store(tmp_path / "platform.db")
    target = SeedKernel(sql, id_minter=lambda _name: "seed-conflict")
    target.create_seed("Different", "alice", "new")

    try:
        migrate_file_registry(home, target=sql)
    except SeedRegistryConflict as exc:
        assert "seed-conflict" in str(exc)
    else:
        raise AssertionError("conflicting Seed registries must refuse import")
