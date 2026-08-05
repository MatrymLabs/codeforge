"""Focused tests for the read-only schema gate shared by CodeForge startup paths."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine, text

from kernel.platform import PlatformStartupError, validate_startup_schema
from kernel.world.db import ArchiveBase


def test_startup_schema_accepts_a_current_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'current.db'}")
    ArchiveBase.metadata.create_all(engine)

    validate_startup_schema(engine)


def test_startup_schema_allows_a_brand_new_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")

    validate_startup_schema(engine)


def test_startup_schema_rejects_an_existing_database_missing_a_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'behind.db'}")
    ArchiveBase.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE audit_events"))

    with pytest.raises(PlatformStartupError, match="audit_events"):
        validate_startup_schema(engine)


@pytest.mark.parametrize("module_name", ["adapters.api", "adapters.web_gateway"])
def test_direct_asgi_startup_uses_the_shared_schema_gate(monkeypatch, module_name):
    module = __import__(module_name, fromlist=["_startup_lifespan", "app"])
    calls: list[str] = []

    def validate() -> None:
        calls.append("validate")

    monkeypatch.setattr("kernel.platform.validate_startup_schema", validate)

    async def run_lifespan() -> None:
        async with module._startup_lifespan(module.app):
            calls.append("running")

    asyncio.run(run_lifespan())

    assert calls == ["validate", "running"]


def test_spark_bootstraps_before_starting_the_gateway(monkeypatch):
    import adapters.cli as cli
    from kernel.seed_selection import SeedSelection

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "_seeds_available", lambda: ["aethryn"])
    monkeypatch.setattr(
        "kernel.seed_selection.resolve_from_environment",
        lambda available, explicit=None: SeedSelection("aethryn", "default"),
    )
    monkeypatch.setattr(
        cli, "_bootstrap_platform", lambda seed, source: calls.append(("bootstrap", seed))
    )
    monkeypatch.setattr("adapters.gateway.serve", lambda: calls.append(("serve", "")))

    cli.spark()

    assert calls == [("bootstrap", "aethryn"), ("serve", "")]
