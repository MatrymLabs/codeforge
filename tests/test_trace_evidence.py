"""CF-401: client-to-deployment correlation evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.jobs import SUCCEEDED, JobRecord
from kernel.seedlab.platform_proof import run_first_platform_proof
from kernel.seedlab.trace_evidence import TraceEvidence, TraceEvidenceError


def test_platform_proof_records_one_safe_correlation_chain(tmp_path: Path) -> None:
    proof = run_first_platform_proof(tmp_path / "proof")
    correlation = f"platform-proof-{proof.seed_id}"
    chain = TraceEvidence(
        correlation_id=correlation,
        session_id=correlation,
        seed_id=proof.seed_id,
        job_id="platform-proof-job",
        worker_id="tool-runner",
        artifact_id=proof.artifact.artifact_id,
        deployment_id=proof.deployment.run_id,
        audit_id="seed-started",
    )
    job = JobRecord(
        job_id="platform-proof-job",
        seed_id=proof.seed_id,
        requested_by=correlation,
        kind="test",
        profile="pytest",
        status=SUCCEEDED,
        created_at="2026-08-04T00:00:00+00:00",
        finished_at="2026-08-04T00:00:01+00:00",
        correlation_id=correlation,
    )
    chain.bind_job(job)
    chain.bind_event(job.event())
    for run in proof.runs:
        chain.bind_tool_run(run)
    chain.bind_artifact(proof.artifact)
    chain.bind_deployment(proof.deployment)
    chain.bind_audit(
        {
            "actor": correlation,
            "action": "test.completed",
            "detail": (
                f'{{"correlation_id":"{correlation}","event_id":"evt-platform-proof",'
                f'"seed_id":"{proof.seed_id}"}}'
            ),
        }
    )
    assert chain.to_dict()["correlation_id"] == correlation
    assert all("password" not in value.lower() for value in chain.to_dict().values())


def test_trace_evidence_rejects_sensitive_or_unscoped_identifiers() -> None:
    with pytest.raises(TraceEvidenceError, match="safe non-empty"):
        TraceEvidence(
            "corr", "user@example.com", "seed", "job", "worker", "artifact", "deploy", "audit"
        )


def test_trace_evidence_rejects_an_audit_entry_from_another_chain() -> None:
    chain = TraceEvidence("corr", "session", "seed", "job", "worker", "artifact", "deploy", "audit")
    with pytest.raises(TraceEvidenceError, match="audit correlation"):
        chain.bind_audit(
            {
                "actor": "session",
                "action": "test.completed",
                "detail": '{"correlation_id":"other","seed_id":"seed"}',
            }
        )


def test_event_bridge_audit_entry_binds_to_trace(tmp_path: Path, monkeypatch) -> None:
    from kernel.seedlab.event_bridge import publish_seed_event
    from kernel.world import audit

    monkeypatch.setenv("CODEFORGE_AUDIT", str(tmp_path / "audit.jsonl"))
    job = JobRecord(
        job_id="job-audit",
        seed_id="seed-audit",
        requested_by="session-audit",
        kind="test",
        profile="fixture",
        status=SUCCEEDED,
        created_at="2026-08-05T12:00:00+00:00",
        finished_at="2026-08-05T12:00:01+00:00",
        correlation_id="corr-audit",
    )
    publish_seed_event(job.event())
    entry = audit.tail(1)[0]
    chain = TraceEvidence(
        "corr-audit",
        "session-audit",
        "seed-audit",
        "job-audit",
        "worker",
        "artifact",
        "deploy",
        "audit",
    )
    chain.bind_audit(entry)


def test_trace_evidence_binds_redacted_worker_logs_and_rejects_secrets() -> None:
    chain = TraceEvidence(
        "corr-log", "session", "seed", "job", "worker", "artifact", "deploy", "audit"
    )
    chain.bind_log(
        {
            "log_id": "log-1",
            "correlation_id": "corr-log",
            "seed_id": "seed",
            "worker_id": "worker",
            "message": "test completed",
        }
    )
    with pytest.raises(TraceEvidenceError, match="sensitive"):
        chain.bind_log(
            {
                "log_id": "log-2",
                "correlation_id": "corr-log",
                "seed_id": "seed",
                "worker_id": "worker",
                "access_token": "must-not-be-recorded",
            }
        )
