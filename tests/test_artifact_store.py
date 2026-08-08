"""Test twin for kernel/seedlab/artifact_store.py."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kernel.seedlab.artifact_store import (
    ArtifactRecord,
    ArtifactStore,
    ArtifactStoreError,
    FileArtifactStore,
    InMemoryArtifactStore,
    artifact_id_for,
    artifact_label,
    artifact_labels,
    build_report_artifacts,
    compare_artifact_reproduction,
    record_generated_artifact,
)
from kernel.seedlab.cli_generator import generate_cli
from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.tool_runner import ToolRunResult


def _model() -> ProjectModel:
    return ProjectModel(
        identity="Task Ledger",
        provenance=Provenance("demo-src", owner="josh", license="MIT", visibility="private"),
        actions=["add"],
    )


def _run(profile: str = "pytest") -> ToolRunResult:
    return ToolRunResult(
        seed_id="seed-1",
        kind="test",
        profile=profile,
        argv=["python", "-m", "pytest"],
        exit_code=0,
        output="1 passed",
        duration=0.1,
        timed_out=False,
        cwd="/workspace/out",
        when="2026-08-04T00:00:00+00:00",
    )


def _record(tmp_path: Path) -> ArtifactRecord:
    artifact = generate_cli(_model(), tmp_path / "out")
    return record_generated_artifact(
        "seed-1",
        artifact,
        runs=(_run("run"), _run("pytest")),
        clock=lambda: "2026-08-04T00:00:00+00:00",
    )


def test_artifact_id_is_stable_and_slugged(tmp_path: Path) -> None:
    artifact = generate_cli(_model(), tmp_path / "out")
    first = artifact_id_for("seed-1", artifact)
    second = artifact_id_for("seed-1", artifact)
    assert first == second
    assert first.startswith("artifact-seed-1-task-ledger-")


def test_artifact_id_keeps_the_full_content_digest(tmp_path: Path) -> None:
    artifact = generate_cli(_model(), tmp_path / "out")
    first = replace(artifact, manifest_hash="sha256:" + "a" * 64)
    second = replace(artifact, manifest_hash="sha256:" + "a" * 12 + "b" * 52)

    assert artifact_id_for("seed-1", first) != artifact_id_for("seed-1", second)


def test_record_generated_artifact_carries_provenance_runs_and_size(tmp_path: Path) -> None:
    record = _record(tmp_path)
    assert record.name == "task-ledger"
    assert record.kind == "cli"
    assert record.provenance.source_id == "demo-src"
    assert record.run_profiles == ("run", "pytest")
    assert record.bytes > 0
    assert record.created_at == "2026-08-04T00:00:00+00:00"
    assert record.deployment_eligible is False


def test_artifact_deployability_requires_complete_evidence(tmp_path: Path) -> None:
    record = record_generated_artifact(
        "seed-1",
        generate_cli(_model(), tmp_path / "out"),
        runs=(_run("pytest"),),
        dependency_lock_digest="sha256:lock",
        sbom={"bomFormat": "CycloneDX", "components": []},
        sbom_status="recorded",
        reproduction_instructions="python -m codeforge.reproduce artifact-1",
        file_ownership={
            path: "generated" for path in generate_cli(_model(), tmp_path / "out-2").files
        },
    )
    assert record.deployment_eligible is True


def test_reproduction_comparison_reports_identical_and_different_outputs(tmp_path: Path) -> None:
    first = _record(tmp_path)
    second = _record(tmp_path / "rerun")
    evidence = compare_artifact_reproduction(first, second)
    assert evidence["same_inputs"] is True and evidence["reproducible"] is True
    changed = replace(second, checksums={**second.checksums, "README.md": "different"})
    assert compare_artifact_reproduction(first, changed)["reproducible"] is False


def test_a_store_is_an_artifact_store() -> None:
    assert isinstance(InMemoryArtifactStore(), ArtifactStore)


def test_inmemory_roundtrip(tmp_path: Path) -> None:
    store = InMemoryArtifactStore()
    record = _record(tmp_path)
    store.save(record)
    assert store.load(record.seed_id, record.artifact_id) == record
    assert store.all_for_seed(record.seed_id) == [record]


def test_file_store_survives_restart(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "artifacts")
    record = _record(tmp_path)
    store.save(record)
    recovered = FileArtifactStore(tmp_path / "artifacts").all_for_seed(record.seed_id)
    assert recovered == [record]


def test_file_store_is_idempotent_but_rejects_evidence_overwrite(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "artifacts")
    record = _record(tmp_path)
    store.save(record)
    store.save(record)
    with pytest.raises(ArtifactStoreError, match="different evidence"):
        store.save(replace(record, model_identity="tampered-model"))


def test_labels_feed_the_project_hub_targets_facet(tmp_path: Path) -> None:
    store = InMemoryArtifactStore()
    record = _record(tmp_path)
    store.save(record)
    label = artifact_label(record)
    assert "task-ledger" in label and "demo-src" in label and "manifest" in label
    assert artifact_labels(store, record.seed_id) == (label,)


def test_build_report_projection_uses_real_artifact_size(tmp_path: Path) -> None:
    record = _record(tmp_path)
    projected = build_report_artifacts([record])[0]
    assert projected["name"] == "task-ledger"
    assert projected["kind"] == "cli"
    assert projected["bytes"] == record.bytes
    assert projected["artifact_id"] == record.artifact_id
    assert projected["source_id"] == "demo-src"
    assert projected["run_profiles"] == ["run", "pytest"]


def test_missing_artifact_file_is_refused(tmp_path: Path) -> None:
    artifact = generate_cli(_model(), tmp_path / "out")
    (Path(artifact.dest) / artifact.files[0]).unlink()
    with pytest.raises(ArtifactStoreError, match="missing"):
        record_generated_artifact("seed-1", artifact)


def test_corrupt_record_raises(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "artifacts")
    seed_dir = store.root / "seed-1"
    seed_dir.mkdir(parents=True)
    (seed_dir / "artifact-bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ArtifactStoreError, match="corrupt"):
        store.load("seed-1", "artifact-bad")


def test_from_dict_refuses_malformed() -> None:
    with pytest.raises(ArtifactStoreError, match="malformed"):
        ArtifactRecord.from_dict({"artifact_id": "a"})
