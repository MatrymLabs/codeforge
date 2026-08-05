"""The HTTP and Telnet adapters must use the configured Seed registry authority."""

from __future__ import annotations

from pathlib import Path

from adapters.api import _seedlab_kernel as api_seedlab_kernel
from adapters.gateway import _GateHandler
from kernel.seedlab.kernel import FileSeedStore, SeedKernel


def test_api_and_gateway_share_sql_seed_registry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    monkeypatch.setenv("SEEDLAB_HOME", str(tmp_path / ".seedlab"))

    created = api_seedlab_kernel().create_seed(
        "Shared API Seed", "alice", "adapter proof", seed_id="seed-adapter"
    )
    gateway_kernel = _GateHandler._workspace_kernel(object.__new__(_GateHandler))

    assert gateway_kernel.get(created.identity.seed_id) == created
    assert [record.identity.seed_id for record in gateway_kernel.list_seeds()] == [
        "seed-adapter"
    ]
    assert not (tmp_path / ".seedlab" / "seeds" / "seed-adapter.json").exists()


def test_api_and_gateway_dual_read_legacy_seed_records(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Legacy Adapter Seed", "alice", "compatibility", seed_id="seed-legacy-adapter"
    )
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql-dual-read")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    monkeypatch.setenv("SEEDLAB_HOME", str(home))

    api_record = api_seedlab_kernel().get("seed-legacy-adapter")
    gateway_record = _GateHandler._workspace_kernel(object.__new__(_GateHandler)).get(
        "seed-legacy-adapter"
    )

    assert api_record == gateway_record
