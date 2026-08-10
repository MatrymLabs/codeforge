"""First local proof that the SeedLab platform loop works end to end.

The proof is intentionally small and original: it creates a Seed from the shipped Engineering Form,
starts the Seed, registers a local source with provenance, extracts and persists a project model,
generates a runnable CLI target, validates the target and its tests, registers the artifact, emits
the same workspace packages the Master Client consumes, takes a verified backup, and proves a fresh
process can recover the Seed/project state from disk.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.seedlab.artifact_store import (
    ArtifactRecord,
    FileArtifactStore,
    artifact_labels,
    build_report_artifacts,
    record_generated_artifact,
)
from kernel.seedlab.backup import INTACT, BackupRef, SeedBackups
from kernel.seedlab.cli_generator import generate_cli, validate_runs, validate_tests
from kernel.seedlab.form import load_definition
from kernel.seedlab.kernel import FileSeedStore, SeedKernel, SeedRecord
from kernel.seedlab.model_store import FileModelStore, model_labels
from kernel.seedlab.project_hub import ProjectHub, ProjectState
from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.source_connector import (
    LocalSource,
    SourceRecord,
    source_connector_label,
    source_label,
)
from kernel.seedlab.source_modeler import model_and_store
from kernel.seedlab.tool_runner import FileRunLog, ToolRunResult, run_labels
from kernel.seedlab.workspace_gmcp import create_from_form_submit, workspace_packages


class PlatformProofError(Exception):
    """The local proof could not complete honestly."""


@dataclass(frozen=True)
class PlatformProofResult:
    """Evidence emitted by the first SeedLab platform proof."""

    seed_id: str
    record: SeedRecord
    source: SourceRecord
    files: tuple[str, ...]
    model: ProjectModel
    runs: tuple[ToolRunResult, ...]
    artifact: ArtifactRecord
    backup: BackupRef
    backup_verdict: str
    hub_text: str
    hub_contract: dict[str, object]
    packages: tuple[tuple[str, dict[str, object]], ...]
    recovered_record: SeedRecord
    recovered_models: tuple[ProjectModel, ...]
    recovered_runs: tuple[ToolRunResult, ...]
    recovered_artifacts: tuple[ArtifactRecord, ...]
    project_state: ProjectState

    def to_dict(self) -> dict[str, object]:
        return {
            "seed_id": self.seed_id,
            "record": self.record.to_dict(),
            "source": {
                "record": {
                    "source_id": self.source.source_id,
                    "owner": self.source.provenance.owner,
                    "license": self.source.provenance.license,
                    "visibility": self.source.provenance.visibility,
                    "allowed_use": self.source.provenance.allowed_use,
                    "root": self.source.root,
                    "file_count": self.source.file_count,
                    "branch": self.source.branch,
                    "commit": self.source.commit,
                },
                "label": source_label(self.source),
                "connector_label": source_connector_label(self.source),
            },
            "files": list(self.files),
            "model": self.model.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
            "artifact": self.artifact.to_dict(),
            "backup": {
                "backup_id": self.backup.backup_id,
                "seed_id": self.backup.seed_id,
                "path": self.backup.path,
                "sha256": self.backup.sha256,
                "when": self.backup.when,
            },
            "backup_verdict": self.backup_verdict,
            "hub_text": self.hub_text,
            "hub_contract": self.hub_contract,
            "packages": [
                {"package": package, "payload": payload} for package, payload in self.packages
            ],
            "recovered_record": self.recovered_record.to_dict(),
            "recovered_models": [model.to_dict() for model in self.recovered_models],
            "recovered_runs": [run.to_dict() for run in self.recovered_runs],
            "recovered_artifacts": [artifact.to_dict() for artifact in self.recovered_artifacts],
            "project_state": {
                "seed_id": self.project_state.seed_id,
                "sources": list(self.project_state.sources),
                "connectors": list(self.project_state.connectors),
                "models": list(self.project_state.models),
                "builds": list(self.project_state.builds),
                "tests": list(self.project_state.tests),
                "targets": list(self.project_state.targets),
                "risks": list(self.project_state.risks),
                "decisions": list(self.project_state.decisions),
            },
        }


def run_first_platform_proof(
    root: Path,
    *,
    owner: str = "josh",
    clock: Callable[[], str] | None = None,
    id_minter: Callable[[str], str] | None = None,
) -> PlatformProofResult:
    """Run the first local Seed proof against durable stores under ``root``."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    clock_fn = clock or _static_clock()

    seed_store = FileSeedStore(root / "seeds")
    kernel = (
        SeedKernel(seed_store, clock=clock_fn, id_minter=id_minter)
        if id_minter is not None
        else SeedKernel(seed_store, clock=clock_fn)
    )
    created = _create_seed_from_form(kernel, owner=owner)
    seed_id = created.identity.seed_id
    record = kernel.start(seed_id, owner)

    source_root = _write_original_source(root / "source")
    source = LocalSource(
        source_root,
        Provenance(
            "first-platform-proof-source",
            owner=owner,
            license="Matrym Labs internal",
            visibility="private",
            allowed_use="local platform proof and generated target validation",
        ),
    )
    source_record = source.register()
    files = tuple(source.list_files())

    model_store = FileModelStore(root / "models")
    model = model_and_store(model_store, seed_id, source)

    generated = generate_cli(model, root / "targets" / seed_id / "cli")
    run_log = FileRunLog(root / "runs")
    runs = (
        validate_runs(generated, seed_id=seed_id),
        validate_tests(generated, seed_id=seed_id),
    )
    for run in runs:
        run_log.append(run)
    if not all(run.ok for run in runs):
        raise PlatformProofError("generated target validation did not pass")

    artifact_store = FileArtifactStore(root / "artifacts")
    artifact = record_generated_artifact(seed_id, generated, runs=runs, clock=clock_fn)
    artifact_store.save(artifact)

    project_state = _project_state(
        seed_id,
        source_record=source_record,
        model_store=model_store,
        run_log=run_log,
        artifact_store=artifact_store,
    )
    hub = ProjectHub(kernel)
    hub_text = hub.render(seed_id, project_state)
    hub_contract = hub.contract(seed_id, project_state)
    artifact_entries = build_report_artifacts(artifact_store.all_for_seed(seed_id))
    packages = tuple(
        workspace_packages(
            record,
            source=source_record,
            files=list(files),
            model=model,
            runs=runs,
            artifacts=artifact_entries,
        )
    )

    backups = SeedBackups(root / "backups", clock=clock_fn)
    backup = backups.backup(record)
    backup_verdict = backups.verify(seed_id, backup.backup_id)
    if backup_verdict != INTACT:
        raise PlatformProofError(f"backup was not intact: {backup_verdict}")

    recovered_kernel = SeedKernel(FileSeedStore(root / "seeds"), clock=clock_fn)
    recovered_record = recovered_kernel.get(seed_id)
    recovered_models = tuple(FileModelStore(root / "models").all_for_seed(seed_id))
    recovered_runs = tuple(FileRunLog(root / "runs").for_seed(seed_id))
    recovered_artifacts = tuple(FileArtifactStore(root / "artifacts").all_for_seed(seed_id))

    return PlatformProofResult(
        seed_id=seed_id,
        record=record,
        source=source_record,
        files=files,
        model=model,
        runs=runs,
        artifact=artifact,
        backup=backup,
        backup_verdict=backup_verdict,
        hub_text=hub_text,
        hub_contract=hub_contract,
        packages=packages,
        recovered_record=recovered_record,
        recovered_models=recovered_models,
        recovered_runs=recovered_runs,
        recovered_artifacts=recovered_artifacts,
        project_state=project_state,
    )


def _create_seed_from_form(kernel: SeedKernel, *, owner: str) -> SeedRecord:
    verdict = create_from_form_submit(
        kernel,
        load_definition(),
        {
            "product_type": "training",
            "answers": {
                "name": "First Platform Proof",
                "owner": "client-supplied-owner-is-ignored",
                "purpose": (
                    "prove local Seed creation, modeling, generation, validation, and recovery"
                ),
                "scenarios": "local CLI target generation",
                "competencies": "Seed lifecycle, source modeling, target generation, validation",
                "certification": False,
            },
        },
        owner=owner,
    )
    if verdict.get("ok") is not True:
        raise PlatformProofError(str(verdict.get("reason") or "Seed creation failed"))
    return kernel.get(str(verdict["id"]))


def _write_original_source(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    package = root / "proof_workload"
    tests = root / "tests"
    package.mkdir(exist_ok=True)
    tests.mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'first-proof-workload'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        '"""Small original workload for the first CodeForge platform proof."""\n',
        encoding="utf-8",
    )
    (package / "core.py").write_text(
        "\n".join(
            [
                "from dataclasses import dataclass",
                "",
                "",
                "@dataclass(frozen=True)",
                "class WorkItem:",
                "    title: str",
                "    done: bool = False",
                "",
                "",
                "def complete(item: WorkItem) -> WorkItem:",
                "    return WorkItem(item.title, True)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tests / "test_core.py").write_text(
        "\n".join(
            [
                "from proof_workload.core import WorkItem, complete",
                "",
                "",
                "def test_complete_marks_item_done():",
                "    assert complete(WorkItem('model source')).done is True",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return root


def _project_state(
    seed_id: str,
    *,
    source_record: SourceRecord,
    model_store: FileModelStore,
    run_log: FileRunLog,
    artifact_store: FileArtifactStore,
) -> ProjectState:
    return ProjectState(
        seed_id,
        sources=(source_label(source_record),),
        connectors=(source_connector_label(source_record),),
        models=model_labels(model_store, seed_id),
        builds=run_labels(run_log, seed_id, "build"),
        tests=run_labels(run_log, seed_id, "test"),
        targets=artifact_labels(artifact_store, seed_id),
        decisions=("First platform proof uses an original local source and generated CLI target.",),
    )


def _static_clock() -> Callable[[], str]:
    return lambda: "2026-08-04T00:00:00+00:00"
