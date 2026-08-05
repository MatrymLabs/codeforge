from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kernel.permission_policy import PermissionDenied, PermissionPolicy, PermissionRule
from kernel.seedlab.creator_draft import (
    APPROVED,
    PUBLISHED,
    REVIEW,
    VALIDATED,
    CreatorDraft,
    CreatorDraftError,
    CreatorDraftStore,
)
from kernel.seedlab.jobs import SUCCEEDED, JobRunner
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.session_identity import SessionIdentity


def test_creator_draft_requires_review_and_independent_publication():
    store = CreatorDraftStore()
    draft = store.create(CreatorDraft("draft-1", "seed-a", "alice", {"name": "Room"}))
    draft = draft.edit("alice", {"description": "A quiet room."})
    draft = draft.transition(VALIDATED, "alice")
    draft = draft.transition(REVIEW, "alice")
    draft = draft.transition(APPROVED, "reviewer")
    with pytest.raises(CreatorDraftError, match="independent"):
        draft.transition(PUBLISHED, "alice")
    draft = store.save(draft.transition(PUBLISHED, "reviewer"))
    assert draft.status == PUBLISHED
    assert draft.version == 6
    assert store.get("draft-1").status == PUBLISHED


def test_published_draft_cannot_be_edited():
    draft = CreatorDraft("draft-2", "seed-a", "alice", {}).transition(VALIDATED, "alice")
    with pytest.raises(CreatorDraftError):
        draft.edit("alice", {"unsafe": True})


def test_test_job_uses_existing_allowlisted_bounded_runner(tmp_path: Path):
    source = LocalSource(
        tmp_path,
        Provenance("job-source", owner="alice", license="Matrym Labs internal"),
    )
    runner = JobRunner(
        source,
        seed_id="seed-a",
        requested_by="alice",
        clock=lambda: "2026-08-05T12:00:00+00:00",
        id_minter=lambda kind: f"job-{kind}-1",
    )
    job = runner.test("python-version")
    assert job.status == SUCCEEDED
    assert job.event().event_type == "test.completed"
    assert job.event().render(accessible=True) == "The test job passed."


def test_test_job_can_enforce_authenticated_session_identity(tmp_path: Path):
    now = datetime.now(UTC)
    identity = SessionIdentity(
        principal_id="alice",
        principal_kind="human",
        session_id="session-alice",
        seed_id="seed-a",
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
        correlation_id="trace-job",
        capabilities=frozenset({"tool.test"}),
    )
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-a"),))
    source = LocalSource(
        tmp_path,
        Provenance("job-source", owner="alice", license="Matrym Labs internal"),
    )
    runner = JobRunner(
        source,
        seed_id="seed-a",
        requested_by="alice",
        identity=identity,
        policy=policy,
    )
    assert runner.test("python-version").status == SUCCEEDED


def test_job_runner_rejects_a_principal_mismatch_before_execution(tmp_path: Path):
    now = datetime.now(UTC)
    identity = SessionIdentity(
        principal_id="alice",
        principal_kind="human",
        session_id="session-alice",
        seed_id="seed-a",
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
        correlation_id="trace-job",
    )
    with pytest.raises(PermissionDenied, match="requested_by"):
        JobRunner(
            LocalSource(tmp_path, Provenance("job-source")),
            seed_id="seed-a",
            requested_by="bob",
            identity=identity,
            policy=PermissionPolicy(),
        )
