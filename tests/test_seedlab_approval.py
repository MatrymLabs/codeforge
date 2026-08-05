from datetime import UTC, datetime
from pathlib import Path

import pytest

from kernel.permission_policy import PermissionPolicy, PermissionRule
from kernel.seedlab.approval import APPROVED, CONSUMED, PENDING, ApprovalError, FileApprovalStore
from kernel.seedlab.jobs import SUCCEEDED, WAITING_APPROVAL, JobRunner
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.session_identity import SessionIdentity


def _identity(*, principal: str = "alice", seed: str = "seed-a") -> SessionIdentity:
    return SessionIdentity(
        principal_id=principal,
        principal_kind="human",
        session_id="session-1",
        seed_id=seed,
        issued_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        correlation_id="corr-1",
        capabilities=frozenset({"job.execute"}),
    )


def _store(tmp_path: Path) -> FileApprovalStore:
    store = FileApprovalStore(tmp_path / "approvals")
    store.request(
        "approval-1",
        job_id="job-1",
        seed_id="seed-a",
        requested_by="alice",
        capability="job.execute",
        scope="seed-a",
        activity_id="activity-1",
        created_at="2026-08-05T12:00:00+00:00",
        expires_at="2099-08-05T13:00:00+00:00",
        evidence_digest="sha256:evidence",
    )
    return store


def test_approval_survives_store_restart_and_requires_independent_approver(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert FileApprovalStore(tmp_path / "approvals").get("approval-1").status == PENDING
    with pytest.raises(ApprovalError, match="independent"):
        store.approve("approval-1", "alice", now="2026-08-05T12:01:00+00:00")
    approved = store.approve("approval-1", "reviewer", now="2026-08-05T12:01:00+00:00")
    assert approved.status == APPROVED


def test_approval_is_revalidated_and_consumed_once(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.approve("approval-1", "reviewer", now="2026-08-05T12:01:00+00:00")
    policy = PermissionPolicy((PermissionRule("job.execute", scope="seed-a"),))
    consumed = store.consume(
        "approval-1",
        identity=_identity(),
        policy=policy,
        job_id="job-1",
        activity_id="activity-1",
        evidence_digest="sha256:evidence",
        now="2026-08-05T12:02:00+00:00",
    )
    assert consumed.status == CONSUMED
    with pytest.raises(ApprovalError, match="not executable"):
        store.consume(
            "approval-1",
            identity=_identity(),
            policy=policy,
            job_id="job-1",
            activity_id="activity-2",
            evidence_digest="sha256:evidence",
            now="2026-08-05T12:03:00+00:00",
        )


def test_job_runner_waits_for_persisted_approval_then_executes_after_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kernel.seedlab import jobs as jobs_module
    from kernel.seedlab.tool_runner import ToolRunResult

    store = _store(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source = LocalSource(source_root, Provenance("source-1", owner="alice", license="internal"))
    monkeypatch.setattr(
        jobs_module,
        "run_tool",
        lambda *args, **kwargs: ToolRunResult(
            seed_id="seed-a",
            kind="test",
            profile="fixture",
            argv=["fixture"],
            exit_code=0,
            output="passed",
            duration=0.01,
            timed_out=False,
            cwd=str(source.root),
            when="2026-08-05T12:02:00+00:00",
        ),
    )
    policy = PermissionPolicy((PermissionRule("job.execute", scope="seed-a"),))
    first = JobRunner(
        source,
        seed_id="seed-a",
        requested_by="alice",
        identity=_identity(),
        policy=policy,
        approval_store=store,
        approval_id="approval-1",
        approval_evidence_digest="sha256:evidence",
        activity_id="activity-1",
        id_minter=lambda kind: "job-1",
    ).test("fixture")
    assert first.status == WAITING_APPROVAL
    store = FileApprovalStore(tmp_path / "approvals")
    store.approve("approval-1", "reviewer", now="2026-08-05T12:01:00+00:00")
    second = JobRunner(
        source,
        seed_id="seed-a",
        requested_by="alice",
        identity=_identity(),
        policy=policy,
        approval_store=store,
        approval_id="approval-1",
        approval_evidence_digest="sha256:evidence",
        activity_id="activity-1",
        id_minter=lambda kind: "job-1",
    ).test("fixture")
    assert second.status == SUCCEEDED
    assert store.get("approval-1").status == CONSUMED
