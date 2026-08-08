from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kernel.hardware_activation import activate_hardware_component
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.permission_policy import PermissionDenied, PermissionPolicy, PermissionRule
from kernel.seedlab.event_bridge import SEED_EVENT_TOPIC, publish_seed_event
from kernel.seedlab.jobs import RUNNING, SUCCEEDED, JobError, JobRecord
from kernel.seedlab.workshop_services import CreatorWorkshopService
from kernel.session_identity import SessionIdentity
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry
from kernel.world import bus


def _workshop_identity(seed_id: str = "seed-one") -> SessionIdentity:
    now = datetime.now(UTC)
    return SessionIdentity(
        principal_id="alice",
        principal_kind="human",
        session_id="workshop-session",
        seed_id=seed_id,
        issued_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
        correlation_id="workshop-trace",
        roles=frozenset({"creator"}),
        capabilities=frozenset({"tool.test"}),
    )


def test_durable_workshop_restores_draft_and_job_and_publishes_event(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEFORGE_AUDIT", str(tmp_path / "audit.jsonl"))
    received: list[dict[str, object]] = []
    bus.reset_bus()
    bus.get_bus().subscribe(SEED_EVENT_TOPIC, received.append)
    try:
        service = CreatorWorkshopService.durable(tmp_path / "workshop")
        service.create_draft("draft-1", "seed-one", "alice", {"name": "Room"})
        service.edit_draft("draft-1", "alice", {"description": "A quiet room."})
        job = service.run_test(
            tmp_path,
            seed_id="seed-one",
            actor_id="alice",
            profile="python-version",
            source_id="internal-fixture",
            source_license="Matrym Labs internal",
        )
        assert job.status == SUCCEEDED
        assert received[-1]["event_type"] == "test.completed"

        recovered = CreatorWorkshopService.durable(tmp_path / "workshop")
        assert recovered.drafts.get("draft-1").payload["description"] == "A quiet room."
        assert recovered.jobs.get(job.job_id).event().correlation_id == job.job_id
        assert recovered.jobs_for_seed("seed-one") == (job,)
    finally:
        bus.reset_bus()


def test_workshop_job_propagates_identity_scope_and_correlation(tmp_path: Path) -> None:
    identity = _workshop_identity()
    policy = PermissionPolicy((PermissionRule("tool.test", scope="seed-one"),))
    service = CreatorWorkshopService.durable(tmp_path / "workshop")

    job = service.run_test(
        tmp_path,
        seed_id="seed-one",
        actor_id="alice",
        profile="python-version",
        source_id="internal-fixture",
        source_license="Matrym Labs internal",
        identity=identity,
        policy=policy,
    )

    assert job.ok
    assert job.requested_by == identity.principal_id
    assert job.correlation_id == identity.correlation_id
    assert job.result is not None and job.result.correlation_id == identity.correlation_id
    with pytest.raises(PermissionDenied, match="scoped to Seed"):
        service.run_test(
            tmp_path,
            seed_id="other-seed",
            actor_id="alice",
            profile="python-version",
            source_id="internal-fixture",
            source_license="Matrym Labs internal",
            identity=identity,
            policy=PermissionPolicy((PermissionRule("tool.test", scope="other-seed"),)),
        )


def test_durable_workshop_replays_a_job_by_idempotency_key_without_rerunning(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workshop"
    first_service = CreatorWorkshopService.durable(root)
    first = first_service.run_test(
        tmp_path,
        seed_id="seed-one",
        actor_id="alice",
        profile="python-version",
        source_id="internal-fixture",
        source_license="Matrym Labs internal",
        idempotency_key="request-1",
    )

    recovered_service = CreatorWorkshopService.durable(root)
    replay = recovered_service.run_test(
        tmp_path,
        seed_id="seed-one",
        actor_id="alice",
        profile="python-version",
        source_id="internal-fixture",
        source_license="Matrym Labs internal",
        idempotency_key="request-1",
    )

    assert replay == first
    assert recovered_service.jobs_for_seed("seed-one") == (first,)
    with pytest.raises(JobError, match="fingerprint"):
        recovered_service.run_test(
            tmp_path,
            seed_id="seed-one",
            actor_id="alice",
            profile="python-version",
            source_id="internal-fixture",
            source_license="Matrym Labs internal",
            idempotency_key="request-1",
            timeout=1.0,
        )


def test_durable_workshop_does_not_rerun_an_interrupted_activity(tmp_path: Path) -> None:
    service = CreatorWorkshopService.durable(tmp_path / "workshop")
    interrupted = JobRecord(
        job_id="job-interrupted",
        seed_id="seed-one",
        requested_by="alice",
        kind="test",
        profile="python-version",
        status=RUNNING,
        created_at="2026-08-05T12:00:00+00:00",
        activity_id="activity-1",
        idempotency_key="request-interrupted",
    )
    service.jobs.save(interrupted)

    replay = service.run_test(
        tmp_path,
        seed_id="seed-one",
        actor_id="alice",
        profile="python-version",
        source_id="internal-fixture",
        source_license="Matrym Labs internal",
        idempotency_key="request-interrupted",
    )

    assert replay == interrupted
    assert service.jobs_for_seed("seed-one") == (interrupted,)


def test_authoritative_shelf_component_runs_for_aethryn_and_second_seed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEFORGE_AUDIT", str(tmp_path / "audit.jsonl"))
    service = CreatorWorkshopService()
    assert "event-ledger" in {part.id for part in service.shelf()}

    registry = HardwareRegistry(tmp_path / "hardware.json")
    record = registry.discover("event-ledger")
    for target in ("validated", "approved", "installed"):
        record = registry.transition(record.component_id, target)

    runtime: PluginRegistry[object] = PluginRegistry()
    activate_hardware_component(
        registry,
        "event-ledger",
        runtime,
        PluginInfo("event-ledger"),
        publish_seed_event,
    )
    registry.register_consumer("event-ledger", "aethryn")
    active = registry.register_consumer("event-ledger", "first-forge")

    current_record = registry.get("event-ledger")
    assert current_record is not None and current_record.state == "active"
    assert set(active.consumers) == {"aethryn", "first-forge"}

    def publish_from_active(event) -> None:
        current = registry.get("event-ledger")
        assert current is not None and current.state == "active"
        publish_seed_event(event)

    service = CreatorWorkshopService(event_publisher=publish_from_active)
    aethryn = service.run_test(
        Path("content/seeds/aethryn"),
        seed_id="aethryn",
        actor_id="matrym",
        profile="python-version",
        source_id="aethryn-seed-package",
        source_license="Matrym Labs internal",
    )
    second = service.run_test(
        Path("content/seeds/first-forge"),
        seed_id="first-forge",
        actor_id="matrym",
        profile="python-version",
        source_id="first-forge-seed-package",
        source_license="Matrym Labs internal",
    )
    assert aethryn.ok and second.ok
    assert aethryn.event().event_type == second.event().event_type == "test.completed"
    assert aethryn.event().seed_id != second.event().seed_id
