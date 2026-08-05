from __future__ import annotations

from pathlib import Path

import pytest

from kernel.event_envelope import EventEnvelope
from kernel.seedlab import jobs as jobs_module
from kernel.seedlab.event_replay import EventReplayError, FileEventReplayStore
from kernel.seedlab.jobs import (
    CANCELLED,
    ERROR,
    FAILED,
    RUNNING,
    SUCCEEDED,
    FileJobStore,
    JobRecord,
    JobRunner,
)
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource
from kernel.seedlab.tool_runner import ToolRunResult
from kernel.seedlab.workshop_services import CreatorWorkshopService


def _event(event_id: str) -> EventEnvelope:
    return EventEnvelope(
        protocol="codeforge.seed",
        version="1.0",
        event_id=event_id,
        seed_id="seed-a",
        session_id="alice",
        event_type="test.completed",
        timestamp="2026-08-05T12:00:00+00:00",
        classification="internal",
        payload={"job_id": event_id},
        text_fallback="Test completed.",
        accessibility_summary="The test completed.",
        correlation_id=event_id,
    )


def test_event_replay_survives_restart_and_supports_cursor(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    first = _event("evt-1")
    second = _event("evt-2")
    FileEventReplayStore(path).append(first)
    FileEventReplayStore(path).append(second)

    recovered = FileEventReplayStore(path)
    assert [event.event_id for event in recovered.replay()] == ["evt-1", "evt-2"]
    assert [event.event_id for event in recovered.replay(after_event_id="evt-1")] == ["evt-2"]
    with pytest.raises(EventReplayError, match="duplicate"):
        recovered.append(first)
    with pytest.raises(EventReplayError, match="unknown replay cursor"):
        recovered.replay(after_event_id="missing")


def test_job_preflight_cancellation_is_bounded_and_auditable(tmp_path: Path) -> None:
    source = LocalSource(tmp_path, Provenance("source-a", owner="alice", license="internal"))
    runner = JobRunner(
        source,
        seed_id="seed-a",
        requested_by="alice",
        cancel_check=lambda: True,
        id_minter=lambda kind: f"cancelled-{kind}",
    )
    job = runner.test("python-version")
    assert job.status == CANCELLED
    assert job.event().event_type == "test.cancelled"
    assert job.result is None


def test_workshop_retries_failed_jobs_as_new_persisted_attempts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEFORGE_AUDIT", str(tmp_path / "audit.jsonl"))
    calls = 0

    def fake_run_tool(*args, **kwargs) -> ToolRunResult:
        nonlocal calls
        calls += 1
        exit_code = 1 if calls == 1 else 0
        return ToolRunResult(
            seed_id="seed-a",
            kind="test",
            profile="fixture",
            argv=["fixture"],
            exit_code=exit_code,
            output="failed" if exit_code else "passed",
            duration=0.01,
            timed_out=False,
            cwd=str(tmp_path),
            when="2026-08-05T12:00:00+00:00",
        )

    monkeypatch.setattr(jobs_module, "run_tool", fake_run_tool)
    service = CreatorWorkshopService.durable(tmp_path / "workshop")
    job = service.run_test(
        tmp_path,
        seed_id="seed-a",
        actor_id="alice",
        profile="fixture",
        source_id="internal-fixture",
        source_license="Matrym Labs internal",
        retries=1,
    )
    assert job.status == SUCCEEDED
    assert job.attempt == 2
    assert job.retry_of
    records = service.jobs_for_seed("seed-a")
    assert [record.status for record in records] == [FAILED, SUCCEEDED]
    assert service.replay_store is not None
    assert len(service.replay_store.replay()) == 2


def test_job_runner_persists_running_checkpoint_before_execution(tmp_path: Path) -> None:
    source = LocalSource(
        tmp_path, Provenance("source-checkpoint", owner="alice", license="internal")
    )
    checkpoints: list[JobRecord] = []
    runner = JobRunner(
        source,
        seed_id="seed-a",
        requested_by="alice",
        checkpoint=checkpoints.append,
        id_minter=lambda kind: f"checkpoint-{kind}",
    )

    job = runner.test("python-version")
    assert checkpoints and checkpoints[0].status == RUNNING
    assert checkpoints[0].job_id == job.job_id
    assert job.status == SUCCEEDED
    assert job.idempotency_key


def test_restart_recovers_running_job_as_error_without_rerunning(tmp_path: Path) -> None:
    store = FileJobStore(tmp_path / "jobs")
    running = JobRecord(
        job_id="job-interrupted",
        seed_id="seed-a",
        requested_by="alice",
        kind="test",
        profile="pytest",
        status=RUNNING,
        created_at="2026-08-05T12:00:00+00:00",
        activity_id="activity-interrupted",
        idempotency_key="test:seed-a:source:pytest",
    )
    store.save(running)

    recovered = FileJobStore(tmp_path / "jobs").recover_interrupted()
    assert len(recovered) == 1
    assert recovered[0].status == ERROR
    assert recovered[0].outcome_reason == "worker restarted"
    assert FileJobStore(tmp_path / "jobs").recover_interrupted() == ()
