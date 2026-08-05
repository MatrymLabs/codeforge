"""Test twin for kernel/seedlab/workspace_contract.py."""

from __future__ import annotations

from pathlib import Path

from kernel.seedlab.deployment import DeploymentProfile, LocalDeploymentController
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.model_store import FileModelStore
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.seedlab.source_modeler import model_and_store
from kernel.seedlab.tool_runner import FileRunLog, run_and_record
from kernel.seedlab.workspace_contract import (
    WORKSPACE_CONTRACT_VERSION,
    build_workspace_contract,
)


def _source(tmp_path: Path) -> LocalSource:
    root = tmp_path / "source"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='workspace'\n", encoding="utf-8")
    return LocalSource(root, Provenance("source-workspace", owner="josh"))


def test_build_workspace_contract_project_and_packages(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    kernel = SeedKernel(FileSeedStore(home / "seeds"), clock=lambda: "2026-08-04T00:00:00+00:00")
    kernel.create_seed("Workspace", "josh", "a workspace", seed_id="seed-workspace")

    source = _source(tmp_path)
    model_store = FileModelStore(home / "models")
    model_and_store(model_store, "seed-workspace", source)
    run_log = FileRunLog(home / "runs")
    run_and_record(run_log, source, "python-version", seed_id="seed-workspace", kind="test")

    contract = build_workspace_contract("seed-workspace", root=home)
    assert contract.contract_version == WORKSPACE_CONTRACT_VERSION
    assert contract.seed["name"] == "Workspace"
    assert contract.project_state["models"]
    assert [item.package for item in contract.packages] == [
        "Project.Status",
        "Model.Schema",
        "Build.Report",
    ]
    assert contract.packages[-1].payload["tests"] == {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
    }


def test_build_workspace_contract_projects_local_deployment_evidence(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    kernel = SeedKernel(FileSeedStore(home / "seeds"), clock=lambda: "2026-08-04T00:00:00+00:00")
    kernel.create_seed("Workspace", "josh", "a workspace", seed_id="seed-workspace")
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "app.txt").write_text("healthy", encoding="utf-8")
    LocalDeploymentController(
        home / "deployments",
        clock=lambda: "2026-08-04T00:01:00+00:00",
        id_minter=iter(["deploy-1"]).__next__,
    ).deploy(DeploymentProfile("local-proof", "seed-workspace", "artifact-1", str(artifact)))

    contract = build_workspace_contract("seed-workspace", root=home)

    deployment = contract.project["deployment"]
    assert isinstance(deployment, dict)
    assert deployment["status"] == "deployed"
    assert deployment["health"] == "healthy"
