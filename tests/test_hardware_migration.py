from pathlib import Path

import pytest

from kernel.hardware_lifecycle import HardwareRegistry
from kernel.hardware_migration import (
    MIGRATION_COMPLETED,
    MIGRATION_ROLLED_BACK,
    HardwareMigrationError,
    HardwareMigrationJournal,
    migrate_hardware_component,
)
from kernel.permission_policy import PermissionContext, PermissionPolicy, PermissionRule
from kernel.seedlab.deployment import (
    DeploymentMigrationBackup,
    DeploymentProfile,
    LocalDeploymentController,
)


def _installed(registry: HardwareRegistry) -> None:
    registry.discover("validator")
    for state in ("validated", "approved", "installed"):
        registry.transition("validator", state)


def _run(registry: HardwareRegistry, journal: HardwareMigrationJournal, root: Path, **overrides):
    ids = iter(("migration-1", "rollback-1"))
    params = {
        "seed_id": "seed-a",
        "backup_reference": "backup://migration-1",
        "preconditions": ("backup verified", "target package signed"),
        "operator_decision": "approved-by-reviewer",
        "migrate": lambda record: (root / "migrated.txt").write_text("new", encoding="utf-8"),
        "health_check": lambda record: True,
        "compensate": lambda record: (root / "migrated.txt").unlink(missing_ok=True),
        "id_minter": lambda prefix: next(ids),
    }
    params.update(overrides)
    return migrate_hardware_component(
        registry,
        journal,
        "validator",
        "2.0.0",
        **params,
    )


def test_migration_persists_version_and_survives_journal_reload(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _installed(registry)
    journal = HardwareMigrationJournal(tmp_path / "lifecycle")

    result = _run(registry, journal, tmp_path)

    assert result.status == MIGRATION_COMPLETED
    assert registry.get("validator").version == "2.0.0"
    assert journal.load_migration("migration-1") == result


def test_failed_health_check_compensates_and_persists_rollback(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _installed(registry)
    journal = HardwareMigrationJournal(tmp_path / "lifecycle")
    calls: list[str] = []

    result = _run(
        registry,
        journal,
        tmp_path,
        health_check=lambda record: False,
        compensate=lambda record: calls.append("compensated"),
    )

    assert result.status == MIGRATION_ROLLED_BACK
    assert result.compensation == "rollback-1"
    assert calls == ["compensated"]
    assert registry.get("validator").version != "2.0.0"
    rollback = journal.load_rollback("rollback-1")
    assert rollback.migration_id == "migration-1"
    assert rollback.status == "completed"


def test_migration_requires_backup_and_named_preconditions(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _installed(registry)
    journal = HardwareMigrationJournal(tmp_path / "lifecycle")
    with pytest.raises(HardwareMigrationError, match="backup_reference"):
        _run(registry, journal, tmp_path, backup_reference="")
    with pytest.raises(HardwareMigrationError, match="named preconditions"):
        _run(registry, journal, tmp_path, preconditions=())


def test_failed_migration_restores_verified_deployment_backup_and_records_authorization(
    tmp_path: Path,
) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _installed(registry)
    journal = HardwareMigrationJournal(tmp_path / "lifecycle")
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "component.txt").write_text("version-one", encoding="utf-8")
    controller = LocalDeploymentController(
        tmp_path / "deployments",
        id_minter=iter(("deploy-1", "restore-1")).__next__,
        clock=lambda: "2026-08-05T18:00:00+00:00",
    )
    controller.deploy(DeploymentProfile("component", "seed-a", "validator", str(artifact)))
    backup = controller.backup_current(
        "component",
        seed_id="seed-a",
        artifact_id="validator",
        backup_id="backup-1",
    )
    policy = PermissionPolicy(
        rules=(PermissionRule("hardware.migrate", scope="seed-a"),)
    )
    permission = PermissionContext(
        "operator",
        capabilities=frozenset({"hardware.migrate"}),
    )

    def mutate(_record) -> None:
        release = controller.current_release("component")
        assert release is not None
        (release / "component.txt").write_text("version-two", encoding="utf-8")

    result = _run(
        registry,
        journal,
        tmp_path,
        migrate=mutate,
        health_check=lambda _record: False,
        compensate=lambda _record: pytest.fail(
            "verified backup should be the compensation path"
        ),
        backup_reference="backup-1",
        backup=DeploymentMigrationBackup(controller, "component"),
        policy=policy,
        permission=permission,
    )

    assert result.status == MIGRATION_ROLLED_BACK
    assert result.authorization == "authorized:hardware.migrate"
    assert registry.get("validator").version == "0.1"
    restored = controller.current_release("component")
    assert restored is not None
    assert (restored / "component.txt").read_text(encoding="utf-8") == "version-one"
    assert journal.load_rollback("rollback-1").backup_reference == backup.backup_id


def test_migration_policy_denial_happens_before_backup_or_mutation(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _installed(registry)
    journal = HardwareMigrationJournal(tmp_path / "lifecycle")

    with pytest.raises(HardwareMigrationError, match="authorization refused"):
        _run(
            registry,
            journal,
            tmp_path,
            policy=PermissionPolicy(),
            permission=PermissionContext("operator", capabilities=frozenset()),
        )

    assert registry.get("validator").version == "0.1"
    assert not (tmp_path / "lifecycle" / "migrations" / "migration-1.json").exists()
