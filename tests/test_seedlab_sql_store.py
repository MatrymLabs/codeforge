"""Contract tests for the SQL-backed generic Seed registry store."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kernel.seedlab.kernel import SeedKernel
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

