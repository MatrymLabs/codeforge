"""Acceptance test for the first local CodeForge platform proof."""

from __future__ import annotations

import json
from pathlib import Path

from kernel.seedlab.backup import INTACT
from kernel.seedlab.platform_proof import run_first_platform_proof
from kernel.seedlab.workspace_gmcp import (
    BUILD_REPORT_PACKAGE,
    MODEL_SCHEMA_PACKAGE,
    PROJECT_STATUS_PACKAGE,
    SOURCE_CONNECTION_PACKAGE,
    SOURCE_TREE_PACKAGE,
)


def test_first_platform_proof_creates_generates_validates_and_recovers(tmp_path: Path) -> None:
    clock_values = iter(f"2026-08-04T00:00:{n:02d}+00:00" for n in range(50))
    result = run_first_platform_proof(
        tmp_path,
        clock=lambda: next(clock_values),
        id_minter=lambda name: "seed-first-proof",
    )

    assert result.seed_id == "seed-first-proof"
    assert result.record.status == "running"
    assert result.record.identity.product_type == "training"
    assert result.record.identity.domain_modules == ("training",)
    assert result.source.provenance.allowed_use.startswith("local platform proof")
    assert "pyproject.toml" in result.files
    assert result.model.identity == "first-proof-workload"
    assert [job.kind for job in result.jobs] == ["build", "test"]
    assert all(job.ok and job.activity_id and job.idempotency_key for job in result.jobs)
    assert result.runs and all(run.ok for run in result.runs)
    assert result.artifact.name == "first-proof-workload"
    assert result.deployment.status == "deployed"
    assert result.deployment.health == "healthy"
    assert result.failed_deployment.status == "failed"
    assert result.failed_deployment.health == "unhealthy"
    assert result.artifact.bytes > 0
    assert result.backup_verdict == INTACT
    assert len(result.semantic_events) == 7
    assert all(
        event.text_fallback and event.accessibility_summary for event in result.semantic_events
    )
    assert result.semantic_release.human_validation == "pending"
    assert not result.semantic_release.release_ready
    assert result.recovered_deployment == result.deployment
    evidence = Path(result.evidence_path)
    assert evidence.is_file()
    saved = json.loads(evidence.read_text(encoding="utf-8"))
    assert saved["seed_id"] == result.seed_id
    assert saved["semantic_events"][-1]["event_type"] == "target.recovered"

    assert "Project Hub :: First Platform Proof" in result.hub_text
    project = result.hub_contract["project"]
    assert isinstance(project, dict)
    assert project["targets"]

    package_names = [package for package, _ in result.packages]
    assert package_names == [
        PROJECT_STATUS_PACKAGE,
        SOURCE_TREE_PACKAGE,
        SOURCE_CONNECTION_PACKAGE,
        MODEL_SCHEMA_PACKAGE,
        BUILD_REPORT_PACKAGE,
    ]
    build_payload = result.packages[-1][1]
    assert build_payload["ok"] is True
    artifacts = build_payload["artifacts"]
    assert isinstance(artifacts, list)
    artifact = artifacts[0]
    assert isinstance(artifact, dict)
    assert artifact["name"] == "first-proof-workload"
    assert artifact["kind"] == "cli"
    assert artifact["bytes"] == result.artifact.bytes
    assert artifact["source_id"] == result.artifact.provenance.source_id
    assert artifact["run_profiles"] == ["run", "pytest"]
    assert result.recovered_record == result.record
    assert result.recovered_models == (result.model,)
    assert result.recovered_jobs == result.jobs
    assert result.recovered_runs == result.runs
    assert result.recovered_artifacts == (result.artifact,)
