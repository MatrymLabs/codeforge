from __future__ import annotations

from pathlib import Path

from kernel.seedlab.artifact_store import ArtifactRecord, FileArtifactStore
from kernel.seedlab.jobs import JobRecord, JobRunner
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.model_store import FileModelStore
from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.seedlab.tool_runner import FileRunLog, ToolRunResult


def _job(root: Path, seed_id: str, owner: str) -> JobRecord:
    root.mkdir(parents=True)
    source = LocalSource(
        root,
        Provenance(f"{seed_id}-source", owner=owner, license="Matrym Labs internal"),
    )
    return JobRunner(
        source,
        seed_id=seed_id,
        requested_by=owner,
        clock=lambda: "2026-08-05T12:00:00+00:00",
        id_minter=lambda kind: f"{seed_id}-{kind}-1",
    ).test("python-version")


def test_same_approved_job_and_event_contract_work_in_two_seeds(tmp_path: Path):
    first = _job(tmp_path / "seed-one", "seed-one", "alice")
    second = _job(tmp_path / "seed-two", "seed-two", "bob")
    assert first.ok and second.ok
    assert first.event().event_type == second.event().event_type == "test.completed"
    assert first.event().payload["job_id"] != second.event().payload["job_id"]
    assert first.event().seed_id != second.event().seed_id


def test_seed_owned_state_isolated_and_recoverable_across_model_run_and_artifact_stores(
    tmp_path: Path,
):
    """Same local record keys remain separate by Seed and survive fresh store instances."""
    seed_store = FileSeedStore(tmp_path / "seeds")
    kernel = SeedKernel(seed_store, clock=lambda: "2026-08-06T12:00:00+00:00")
    kernel.create_seed("First", "alice", "one", seed_id="seed-one")
    kernel.create_seed("Second", "bob", "two", seed_id="seed-two")

    provenance = Provenance("shared-source", owner="Matrym Labs", license="internal")
    models = FileModelStore(tmp_path / "models")
    models.save("seed-one", "shared-model", ProjectModel("one", provenance))
    models.save("seed-two", "shared-model", ProjectModel("two", provenance))

    runs = FileRunLog(tmp_path / "runs")
    runs.append(
        ToolRunResult(
            seed_id="seed-one",
            kind="test",
            profile="python-version",
            argv=["python", "--version"],
            exit_code=0,
            output="one",
            duration=0.1,
            timed_out=False,
            cwd=str(tmp_path),
            when="2026-08-06T12:00:00+00:00",
        )
    )
    runs.append(
        ToolRunResult(
            seed_id="seed-two",
            kind="test",
            profile="python-version",
            argv=["python", "--version"],
            exit_code=0,
            output="two",
            duration=0.1,
            timed_out=False,
            cwd=str(tmp_path),
            when="2026-08-06T12:00:00+00:00",
        )
    )

    artifacts = FileArtifactStore(tmp_path / "artifacts")
    for seed_id, label in (("seed-one", "one"), ("seed-two", "two")):
        artifacts.save(
            ArtifactRecord(
                artifact_id="shared-artifact",
                seed_id=seed_id,
                name=label,
                kind="cli",
                path=f"{seed_id}/artifact",
                files=("main.py",),
                checksums={"main.py": f"sha256:{label}"},
                manifest_hash=f"manifest-{label}",
                provenance=provenance,
                model_identity=label,
            )
        )

    recovered_kernel = SeedKernel(FileSeedStore(tmp_path / "seeds"))
    recovered_models = FileModelStore(tmp_path / "models")
    recovered_runs = FileRunLog(tmp_path / "runs")
    recovered_artifacts = FileArtifactStore(tmp_path / "artifacts")

    assert {record.identity.seed_id for record in recovered_kernel.list_seeds()} == {
        "seed-one",
        "seed-two",
    }
    assert [model.identity for model in recovered_models.all_for_seed("seed-one")] == ["one"]
    assert [model.identity for model in recovered_models.all_for_seed("seed-two")] == ["two"]
    assert [run.output for run in recovered_runs.for_seed("seed-one")] == ["one"]
    assert [run.output for run in recovered_runs.for_seed("seed-two")] == ["two"]
    assert recovered_artifacts.load("seed-one", "shared-artifact").name == "one"
    assert recovered_artifacts.load("seed-two", "shared-artifact").name == "two"
    assert recovered_artifacts.load("seed-one", "missing") is None
