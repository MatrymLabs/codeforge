"""Operational evidence slice for CF-304."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from kernel.hardware_lifecycle import HardwareRegistry
from kernel.hardware_migration import (
    MIGRATION_COMPLETED,
    HardwareMigrationJournal,
    migrate_hardware_component,
)
from kernel.seedlab.backup import INTACT, SeedBackups, restore
from kernel.seedlab.jobs import SUCCEEDED, FileJobStore, JobRecord
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.operational_baseline import (
    EVIDENCE_ONLY,
    PASSED,
    OperationalBaseline,
    OperationalCheck,
    render_baseline,
)
from kernel.service_health import ServiceHealth
from kernel.shelf import trace
from kernel.shelf.observability import METRICS


def test_aethryn_operational_baseline_exercises_real_platform_evidence(tmp_path: Path) -> None:
    """Record the six required checks and recover the packet from durable storage."""
    seed_id = "aethryn"
    checks: list[OperationalCheck] = []

    # Concurrent actions: independent durable job records remain complete and parseable when
    # several workers write at the same time.
    jobs = FileJobStore(tmp_path / "jobs")

    def save_job(number: int) -> None:
        jobs.save(
            JobRecord(
                job_id=f"ops-{number:02d}",
                seed_id=seed_id,
                requested_by="ops-test",
                kind="test",
                profile="pytest",
                status=SUCCEEDED,
                created_at=f"2026-08-05T00:00:{number:02d}Z",
                finished_at=f"2026-08-05T00:00:{number:02d}Z",
            )
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save_job, range(24)))
    persisted_jobs = jobs.for_seed(seed_id)
    assert len(persisted_jobs) == 24
    checks.append(
        OperationalCheck(
            "concurrent_actions", PASSED, f"{tmp_path / 'jobs'}: 24 concurrent records reloaded"
        )
    )

    # Persistence migration: the governed Hardware migration journal records the version change
    # and the health result, rather than treating an in-memory update as evidence.
    registry = HardwareRegistry(tmp_path / "hardware.json")
    registry.discover("validator")
    for state in ("validated", "approved", "installed"):
        registry.transition("validator", state)
    journal = HardwareMigrationJournal(tmp_path / "migration")
    migration = migrate_hardware_component(
        registry,
        journal,
        "validator",
        "2.0.0",
        seed_id=seed_id,
        backup_reference="backup://aethryn-ops",
        preconditions=("backup verified", "package signed"),
        operator_decision="approved-by-ops-review",
        migrate=lambda _record: None,
        health_check=lambda _record: True,
        compensate=lambda _record: None,
        id_minter=lambda prefix: f"{prefix}-ops",
        clock=lambda: "2026-08-05T00:01:00Z",
    )
    assert migration.status == MIGRATION_COMPLETED
    assert journal.load_migration("migration-ops").health == "healthy"
    checks.append(
        OperationalCheck(
            "persistence_migration", PASSED, f"{tmp_path / 'migration'}: validator 1.0.0→2.0.0"
        )
    )

    # Backup and restore: restore routes through the Seed Kernel, so the recovery itself is audited.
    kernel = SeedKernel(FileSeedStore(tmp_path / "seeds"), id_minter=lambda _name: "aethryn-ops")
    kernel.create_seed("Aethryn Operations", "ops", "operational baseline", seed_id=seed_id)
    running = kernel.start(seed_id, "ops")
    backups = SeedBackups(tmp_path / "backups", clock=lambda: "2026-08-05T00:02:00Z")
    backup = backups.backup(running)
    assert backups.verify(seed_id, backup.backup_id) == INTACT
    kernel.stop(seed_id, "ops")
    restored = restore(kernel, backups, seed_id, backup.backup_id, "ops")
    assert restored.status == "running"
    checks.append(
        OperationalCheck(
            "backup_restore", PASSED, f"{backup.path}: {backups.verify(seed_id, backup.backup_id)}"
        )
    )

    # Health: unknown and failed dependencies cannot be reported ready; this baseline contains only
    # concrete healthy checks.
    health = ServiceHealth()
    health.add_bool("seed-store", lambda: FileSeedStore(tmp_path / "seeds").root.is_dir())
    health.add_bool("hardware-journal", lambda: (tmp_path / "migration" / "migrations").is_dir())
    assert health.ready()
    checks.append(OperationalCheck("health", PASSED, health.report()))

    # Telemetry: one trace crosses a boundary and a bounded metric is emitted with a stable route.
    METRICS.reset()
    parent = trace.start_trace(rng=lambda n: "a" * (n * 2))
    child = trace.continue_trace(parent.traceparent(), rng=lambda n: "b" * (n * 2))
    METRICS.observe("GET", "/health", 200, 0.001)
    metrics = METRICS.render()
    assert child.trace_id == parent.trace_id and child.parent_span_id == parent.span_id
    assert 'route="/health"' in metrics
    checks.append(OperationalCheck("telemetry", PASSED, "traceparent + Prometheus /health series"))

    # Recovery: a fresh Kernel and JobStore read the same durable state after the prior operations.
    recovered_kernel = SeedKernel(FileSeedStore(tmp_path / "seeds"))
    recovered_jobs = FileJobStore(tmp_path / "jobs")
    assert recovered_kernel.get(seed_id).status == "running"
    assert len(recovered_jobs.for_seed(seed_id)) == 24
    checks.append(
        OperationalCheck(
            "recovery",
            PASSED,
            f"fresh Kernel/JobStore: {len(recovered_jobs.for_seed(seed_id))} jobs",
        )
    )

    baseline = OperationalBaseline(
        baseline_id="aethryn-ops-2026-08-05",
        seed_id=seed_id,
        started_at="2026-08-05T00:00:00Z",
        completed_at="2026-08-05T00:03:00Z",
        checks=tuple(checks),
        limitations=(
            "single-host evidence only",
            "no MMORPG-scale capacity result",
            "no multi-region or disaster-recovery claim",
            "not production-ready",
        ),
    )
    target = tmp_path / "baseline.json"
    baseline.save(target)
    recovered_baseline = OperationalBaseline.load(target)
    assert recovered_baseline.readiness == EVIDENCE_ONLY
    assert recovered_baseline.passed
    assert "not production-ready" in render_baseline(recovered_baseline)
