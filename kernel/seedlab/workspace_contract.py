"""SeedLab workspace contract: one versioned JSON shape for client panels.

This is the structured client-facing layer over the existing SeedLab projections. It packages the
current Project Hub contract, a normalized project-state snapshot, and the live workspace packages
that the Master Client can render.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.blueprint import Blueprint
from kernel.seed_package import BuildManifest
from kernel.seedlab.artifact_store import (
    ArtifactRecord,
    ArtifactStore,
    artifact_labels,
    build_report_artifacts,
)
from kernel.seedlab.kernel import BlueprintKernel, FileSeedStore
from kernel.seedlab.model_store import FileModelStore, ModelStore, model_labels
from kernel.seedlab.project_hub import ProjectHub, ProjectState
from kernel.seedlab.project_model import ProjectModel
from kernel.seedlab.source_connector import SourceRecord, source_connector_label, source_label
from kernel.seedlab.tool_runner import FileRunLog, ToolRunResult, run_labels
from kernel.seedlab.workspace_gmcp import workspace_packages

WORKSPACE_CONTRACT_VERSION = "seedlab.workspace/1"


@dataclass(frozen=True)
class WorkspacePackageRecord:
    """One package in the structured workspace contract."""

    package: str
    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {"package": self.package, "payload": self.payload}


@dataclass(frozen=True)
class WorkspaceContract:
    """Versioned workspace contract for the Master Client."""

    contract_version: str
    seed: dict[str, object]
    project: dict[str, object]
    project_state: dict[str, object]
    packages: tuple[WorkspacePackageRecord, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "seed": self.seed,
            "project": self.project,
            "project_state": self.project_state,
            "packages": [package.to_dict() for package in self.packages],
        }


def _default_home(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root)
    return Path(os.environ.get("SEEDLAB_HOME", ".seedlab"))


def _seed_kernel(root: Path | None = None) -> BlueprintKernel:
    home = _default_home(root)
    return BlueprintKernel(FileSeedStore(home / "seeds"))


def _project_state(
    seed_id: str,
    *,
    source: SourceRecord | None = None,
    model_store: ModelStore,
    run_log: FileRunLog,
    artifact_store: ArtifactStore,
) -> ProjectState:
    source_labels: tuple[str, ...] = ()
    connector_labels: tuple[str, ...] = ()
    if source is not None:
        source_labels = (source_label(source),)
        connector_labels = (source_connector_label(source),)
    return ProjectState(
        seed_id,
        sources=source_labels,
        connectors=connector_labels,
        models=model_labels(model_store, seed_id),
        builds=run_labels(run_log, seed_id, "build"),
        tests=run_labels(run_log, seed_id, "test"),
        targets=artifact_labels(artifact_store, seed_id),
    )


def build_workspace_contract(
    seed_id: str,
    *,
    root: Path | None = None,
    source: SourceRecord | None = None,
    source_files: Sequence[str] | None = None,
    model: ProjectModel | None = None,
    runs: Sequence[ToolRunResult] | None = None,
    artifacts: Sequence[ArtifactRecord] | None = None,
    blueprints: Sequence[Blueprint] | None = None,
    manifest: BuildManifest | None = None,
    modules: Sequence[Mapping[str, object]] | None = None,
    findings: Sequence[Mapping[str, object]] | None = None,
) -> WorkspaceContract:
    """Build the client-facing workspace contract from the existing SeedLab projections."""
    home = _default_home(root)
    kernel = _seed_kernel(home)
    record = kernel.get(seed_id)
    model_store = FileModelStore(home / "models")
    run_log = FileRunLog(home / "runs")
    artifact_store = _artifact_store(home / "artifacts")

    state = _project_state(
        seed_id,
        source=source,
        model_store=model_store,
        run_log=run_log,
        artifact_store=artifact_store,
    )
    project = ProjectHub(kernel).contract(seed_id, state=state)
    model_list = model
    if model_list is None:
        seeded_models = model_store.all_for_seed(seed_id)
        if seeded_models:
            model_list = seeded_models[-1]
    run_list = None if runs is None else list(runs)
    artifact_list = None if artifacts is None else list(artifacts)
    blueprint_list = None if blueprints is None else list(blueprints)
    manifest_value = manifest
    module_list = None if modules is None else list(modules)
    finding_list = None if findings is None else list(findings)

    packages = workspace_packages(
        record,
        source=source,
        files=list(source_files or []),
        model=model_list,
        runs=run_list if run_list is not None else run_log.for_seed(seed_id),
        artifacts=build_report_artifacts(
            artifact_list if artifact_list is not None else artifact_store.all_for_seed(seed_id)
        ),
        blueprints=blueprint_list,
        manifest=manifest_value,
        modules=module_list,
        findings=finding_list,
    )
    seed: dict[str, object] = {
        "id": record.identity.seed_id,
        "name": record.identity.name,
        "owner": record.identity.owner,
        "status": record.status,
        "purpose": record.identity.purpose,
    }
    return WorkspaceContract(
        contract_version=WORKSPACE_CONTRACT_VERSION,
        seed=seed,
        project=project,
        project_state={
            "seed_id": state.seed_id,
            "sources": list(state.sources),
            "connectors": list(state.connectors),
            "models": list(state.models),
            "builds": list(state.builds),
            "tests": list(state.tests),
            "targets": list(state.targets),
            "risks": list(state.risks),
            "decisions": list(state.decisions),
        },
        packages=tuple(WorkspacePackageRecord(package, payload) for package, payload in packages),
    )


def _artifact_store(root: Path) -> ArtifactStore:
    from kernel.seedlab.artifact_store import FileArtifactStore

    return FileArtifactStore(root)
