"""Configured SeedLab run evidence is shared by API and workspace projections."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from adapters.api import _seedlab_kernel, _seedlab_run_log
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.tool_runner import (
    DualReadRunLog,
    FileRunLog,
    SqlRunLog,
    ToolRunResult,
)
from kernel.seedlab.workspace_contract import build_workspace_contract
from kernel.world.db import ArchiveBase


def _result(seed_id: str, *, kind: str = "test", profile: str = "pytest") -> ToolRunResult:
    return ToolRunResult(
        seed_id=seed_id,
        kind=kind,
        profile=profile,
        argv=["python", "-m", profile],
        exit_code=0,
        output="passed",
        duration=0.25,
        timed_out=False,
        cwd="/workspace",
        when="2026-08-05T00:00:00+00:00",
    )


def test_sql_run_log_survives_restart_and_preserves_order(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    first = _result("seed-1", profile="first")
    second = _result("seed-1", kind="build", profile="second")
    store = SqlRunLog(lambda: Session(engine))

    store.append(first)
    store.append(second)

    recovered = SqlRunLog(lambda: Session(engine)).for_seed("seed-1")

    assert recovered == [first, second]
    assert SqlRunLog(lambda: Session(engine)).for_seed("seed-other") == []


def test_dual_read_run_log_appends_sql_and_deduplicates_legacy(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    home = tmp_path / ".seedlab"
    legacy = FileRunLog(home / "runs")
    result = _result("seed-1")
    legacy.append(result)
    store = DualReadRunLog(SqlRunLog(lambda: Session(engine)), legacy)

    assert store.for_seed("seed-1") == [result]
    store.append(_result("seed-1", kind="build", profile="build"))

    assert [run.kind for run in store.for_seed("seed-1")] == ["build", "test"]


def test_api_and_workspace_contract_share_sql_run_evidence(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    _seedlab_kernel().create_seed("SQL Runs", "alice", "run authority", seed_id="seed-sql-runs")
    _seedlab_run_log().append(_result("seed-sql-runs"))

    contract = build_workspace_contract("seed-sql-runs", root=home)

    assert contract.project_state["tests"]
    assert "pytest exit=0" in contract.project_state["tests"][0]
    assert not (home / "runs" / "seed-sql-runs.jsonl").exists()


def test_workspace_contract_dual_reads_legacy_run_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql-dual-read")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Legacy Runs", "alice", "compatibility", seed_id="seed-legacy-runs"
    )
    FileRunLog(home / "runs").append(_result("seed-legacy-runs"))

    contract = build_workspace_contract("seed-legacy-runs", root=home)

    assert "pytest exit=0" in contract.project_state["tests"][0]
