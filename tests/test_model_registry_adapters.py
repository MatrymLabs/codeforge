"""HTTP and workspace-contract model projections use the configured model authority."""

from __future__ import annotations

from pathlib import Path

from adapters.api import _seedlab_kernel, _seedlab_model_store
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.workspace_contract import build_workspace_contract


def _model() -> ProjectModel:
    return ProjectModel(
        identity="SQL Model",
        provenance=Provenance("source-sql", owner="alice"),
        entities=["Task"],
    )


def test_api_and_workspace_contract_share_sql_model_store(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    _seedlab_kernel().create_seed(
        "SQL Workspace", "alice", "model authority", seed_id="seed-sql-model"
    )
    model = _model()
    _seedlab_model_store().save("seed-sql-model", "model-sql", model)

    contract = build_workspace_contract("seed-sql-model", root=home)

    assert contract.project_state["models"]
    assert "SQL Model" in contract.project_state["models"][0]
    assert not (home / "models" / "seed-sql-model" / "model-sql.json").exists()


def test_workspace_contract_dual_reads_legacy_models(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.setenv("CODEFORGE_SEED_REGISTRY", "sql-dual-read")
    monkeypatch.setenv("CODEFORGE_DB", str(tmp_path / "codeforge.db"))
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Legacy Workspace", "alice", "compatibility", seed_id="seed-legacy-model"
    )
    from kernel.seedlab.model_store import FileModelStore, model_id_for

    model = _model()
    FileModelStore(home / "models").save("seed-legacy-model", model_id_for(model), model)

    contract = build_workspace_contract("seed-legacy-model", root=home)

    assert "SQL Model" in contract.project_state["models"][0]
