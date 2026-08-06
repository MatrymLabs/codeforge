from datetime import UTC, datetime
from pathlib import Path

import pytest

from kernel.ai_orchestration import (
    APPROVED,
    AWAITING_REVIEW,
    COMPLETED,
    AIJobBinding,
    AIOrchestrationError,
    AIOrchestrator,
    AIProviderManifest,
    FileAIRunStore,
    ToolGrant,
)
from kernel.permission_policy import PermissionPolicy, PermissionRule
from kernel.seedlab.jobs import JobRecord
from kernel.session_identity import SessionIdentity


def _identity(principal: str = "alice", kind: str = "human") -> SessionIdentity:
    return SessionIdentity(
        principal_id=principal,
        principal_kind=kind,
        session_id="session-ai",
        seed_id="seed-ai",
        issued_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        correlation_id="corr-ai",
        capabilities=frozenset({"ai.run", "ai.tool.repository.read"}),
    )


def _policy() -> PermissionPolicy:
    return PermissionPolicy(
        (
            PermissionRule("ai.run", scope="seed-ai"),
            PermissionRule("ai.tool.repository.read", scope="seed-ai"),
        )
    )


def _grant() -> ToolGrant:
    return ToolGrant(
        tool_id="repository.read",
        seed_id="seed-ai",
        principal_id="alice",
        actions=("read", "search"),
        scope=("src/approved/**",),
        denied=("write", "execute", "access_secrets"),
        expires_at="2099-01-01T00:00:00+00:00",
    )


def test_tool_grant_enforces_seed_scope_action_resource_and_policy() -> None:
    grant = _grant()
    grant.assert_allowed(
        identity=_identity(),
        policy=_policy(),
        action="read",
        resource="src/approved/file.py",
    )
    with pytest.raises(AIOrchestrationError, match="outside the grant scope"):
        grant.assert_allowed(
            identity=_identity(), policy=_policy(), action="read", resource="src/private/**"
        )
    with pytest.raises(AIOrchestrationError, match="not granted"):
        grant.assert_allowed(
            identity=_identity(), policy=_policy(), action="execute", resource="src/approved/**"
        )


def test_ai_run_requires_review_for_escalated_autonomy_and_survives_restart(tmp_path: Path) -> None:
    store = FileAIRunStore(tmp_path / "ai-runs")
    audit_entries: list[tuple[str, str, str]] = []
    def audit_sink(actor: str, action: str, detail: str) -> None:
        audit_entries.append((actor, action, detail))

    orchestrator = AIOrchestrator(store, audit_sink)
    run = orchestrator.request(
        provider=AIProviderManifest("provider-a", "model-a", "1", ("text",)),
        task="propose a validator change",
        identity=_identity(),
        policy=_policy(),
        context_digest="sha256:context",
        prompt_digest="sha256:prompt",
        requested_autonomy="reviewer",
        context_flags={"security_sensitive"},
        tool_grants=(_grant(),),
        ai_run_id="ai-run-1",
    )
    assert run.status == AWAITING_REVIEW and run.allowed_autonomy == "reviewer"
    assert run.audit_id and audit_entries[0][1] == "ai.requested"
    recovered = FileAIRunStore(tmp_path / "ai-runs").get("ai-run-1")
    assert recovered.correlation_id == "corr-ai"

    with pytest.raises(AIOrchestrationError, match="independent"):
        orchestrator.approve("ai-run-1", _identity(), policy=_policy())
    approved = orchestrator.approve("ai-run-1", _identity("reviewer"), policy=_policy())
    assert approved.status == APPROVED
    completed = orchestrator.record_output(
        "ai-run-1",
        identity=_identity(),
        policy=_policy(),
        output="candidate",
        citations=("source:1",),
        evaluations=("human-reviewed",),
    )
    assert completed.status == COMPLETED
    assert len(audit_entries) == 3


def test_ai_run_rejects_policy_capped_autonomy_and_nonhuman_reviewer(tmp_path: Path) -> None:
    orchestrator = AIOrchestrator(FileAIRunStore(tmp_path / "ai-runs"))
    with pytest.raises(AIOrchestrationError, match="requested autonomy is denied"):
        orchestrator.request(
            provider=AIProviderManifest("provider-a", "model-a", "1"),
            task="deploy",
            identity=_identity(),
            policy=_policy(),
            context_digest="context",
            prompt_digest="prompt",
            requested_autonomy="executor",
            context_flags={"production_without_tested_rollback"},
        )
    run = orchestrator.request(
        provider=AIProviderManifest("provider-a", "model-a", "1"),
        task="review",
        identity=_identity(),
        policy=_policy(),
        context_digest="context",
        prompt_digest="prompt",
        requested_autonomy="reviewer",
        ai_run_id="ai-run-reviewer",
    )
    assert run.status == AWAITING_REVIEW
    with pytest.raises(AIOrchestrationError, match="human reviewer"):
        orchestrator.approve(
            run.ai_run_id,
            _identity("agent-reviewer", "agent"),
            policy=_policy(),
        )


def test_ai_run_denies_missing_capability_and_expired_grant(tmp_path: Path) -> None:
    with pytest.raises(AIOrchestrationError, match="no grant"):
        AIOrchestrator(FileAIRunStore(tmp_path / "ai-runs")).request(
            provider=AIProviderManifest("provider-a", "model-a", "1"),
            task="inspect",
            identity=_identity(),
            policy=PermissionPolicy((PermissionRule("other", scope="seed-ai"),)),
            context_digest="context",
            prompt_digest="prompt",
        )
    expired = ToolGrant(
        tool_id="repository.read",
        seed_id="seed-ai",
        principal_id="alice",
        actions=("read",),
        expires_at="2020-01-01T00:00:00+00:00",
    )
    with pytest.raises(AIOrchestrationError, match="expired"):
        expired.assert_allowed(
            identity=_identity(),
            policy=_policy(),
            action="read",
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_ai_run_binds_existing_durable_job_evidence(tmp_path: Path) -> None:
    orchestrator = AIOrchestrator(FileAIRunStore(tmp_path / "ai-runs"))
    run = orchestrator.request(
        provider=AIProviderManifest("provider-a", "model-a", "1"),
        task="propose a validator change",
        identity=_identity(),
        policy=_policy(),
        context_digest="context",
        prompt_digest="prompt",
        ai_run_id="ai-run-job",
    )
    job = JobRecord(
        job_id="job-test-1",
        seed_id="seed-ai",
        requested_by="alice",
        kind="test",
        profile="pytest",
        status="succeeded",
        created_at="2026-01-01T00:00:00+00:00",
        correlation_id="corr-ai",
    )
    bound = orchestrator.bind_job(
        run.ai_run_id,
        job,
        identity=_identity(),
        policy=_policy(),
    )
    assert bound.job_bindings == (AIJobBinding("job-test-1", "seed-ai", "corr-ai", "succeeded"),)
    recovered = FileAIRunStore(tmp_path / "ai-runs").get(run.ai_run_id)
    assert recovered.job_bindings == bound.job_bindings
    assert (
        orchestrator.bind_job(run.ai_run_id, job, identity=_identity(), policy=_policy()) == bound
    )


def test_ai_run_rejects_cross_seed_or_cross_correlation_job_binding(tmp_path: Path) -> None:
    orchestrator = AIOrchestrator(FileAIRunStore(tmp_path / "ai-runs"))
    run = orchestrator.request(
        provider=AIProviderManifest("provider-a", "model-a", "1"),
        task="inspect",
        identity=_identity(),
        policy=_policy(),
        context_digest="context",
        prompt_digest="prompt",
        ai_run_id="ai-run-job-scope",
    )
    bad_job = JobRecord(
        job_id="job-test-bad",
        seed_id="other-seed",
        requested_by="alice",
        kind="test",
        profile="pytest",
        status="succeeded",
        created_at="2026-01-01T00:00:00+00:00",
        correlation_id="other-correlation",
    )
    with pytest.raises(AIOrchestrationError, match="Seed scope"):
        orchestrator.bind_job(run.ai_run_id, bad_job, identity=_identity(), policy=_policy())
