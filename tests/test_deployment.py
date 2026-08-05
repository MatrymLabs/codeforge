from pathlib import Path

import pytest

from kernel.seedlab.deployment import (
    DEPLOYED,
    FAILED,
    ROLLED_BACK,
    DeploymentError,
    DeploymentProfile,
    LocalDeploymentController,
)


def _profile(source: Path) -> DeploymentProfile:
    return DeploymentProfile(
        profile_id="local-proof",
        seed_id="seed-proof",
        artifact_id="artifact-proof-1",
        artifact_path=str(source),
    )


def test_local_deployment_stages_health_checks_and_survives_restart(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    (source / "app.txt").write_text("version one", encoding="utf-8")
    controller = LocalDeploymentController(
        tmp_path / "deployments", id_minter=iter(["deploy-1"]).__next__
    )

    run = controller.deploy(_profile(source))

    assert run.status == DEPLOYED and run.health == "healthy"
    assert Path(run.release_path).joinpath("app.txt").read_text() == "version one"
    recovered = LocalDeploymentController(tmp_path / "deployments")
    assert recovered.current_release("local-proof") == Path(run.release_path).resolve()
    assert recovered.get_run("deploy-1") == run


def test_failed_health_check_does_not_replace_current_release(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    (source / "app.txt").write_text("bad", encoding="utf-8")
    controller = LocalDeploymentController(
        tmp_path / "deployments",
        id_minter=iter(["deploy-bad"]).__next__,
        health_checks={"reject": lambda path: False},
    )
    profile = DeploymentProfile(
        profile_id="local-proof",
        seed_id="seed-proof",
        artifact_id="artifact-proof-bad",
        artifact_path=str(source),
        health_check="reject",
    )

    run = controller.deploy(profile)

    assert run.status == FAILED and run.health == "unhealthy"
    assert controller.current_release("local-proof") is None


def test_successful_update_can_roll_back_to_the_previous_release(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    file = source / "app.txt"
    file.write_text("one", encoding="utf-8")
    ids = iter(["deploy-1", "deploy-2", "rollback-1"])
    controller = LocalDeploymentController(tmp_path / "deployments", id_minter=ids.__next__)
    first = controller.deploy(_profile(source))
    file.write_text("two", encoding="utf-8")
    second = controller.deploy(_profile(source))

    rollback = controller.rollback(second.run_id)

    assert first.status == DEPLOYED and second.status == DEPLOYED
    assert rollback.status == ROLLED_BACK
    current = controller.current_release("local-proof")
    assert current == Path(first.release_path).resolve()
    assert current is not None and (current / "app.txt").read_text() == "one"


def test_profile_rejects_non_local_targets_and_unknown_checks(tmp_path: Path) -> None:
    with pytest.raises(DeploymentError, match="only target 'local'"):
        DeploymentProfile("p", "s", "a", str(tmp_path), target="cloud")
    source = tmp_path / "artifact"
    source.mkdir()
    controller = LocalDeploymentController(tmp_path / "deployments")
    profile = DeploymentProfile("p", "s", "a", str(source), health_check="missing")
    with pytest.raises(DeploymentError, match="unknown health check"):
        controller.deploy(profile)


def test_deployment_backup_restores_exact_release_and_state(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    (source / "app.txt").write_text("version one", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    (state / "world.json").write_text('{"version": 1}', encoding="utf-8")
    controller = LocalDeploymentController(
        tmp_path / "deployments", id_minter=iter(["deploy-1", "restore-1"]).__next__
    )
    deployed = controller.deploy(_profile(source))
    backup = controller.backup_current(
        "local-proof",
        seed_id="seed-proof",
        artifact_id="artifact-proof-1",
        state_path=state,
        backup_id="backup-1",
    )
    assert controller.verify_backup("local-proof", "backup-1") == backup

    Path(deployed.release_path, "app.txt").write_text("corrupted", encoding="utf-8")
    (state / "world.json").write_text('{"version": 99}', encoding="utf-8")
    restored = controller.restore_backup("local-proof", "backup-1", state_path=state)

    assert restored.status == ROLLED_BACK and restored.backup_reference == "backup-1"
    current = controller.current_release("local-proof")
    assert current is not None and (current / "app.txt").read_text() == "version one"
    assert (state / "world.json").read_text() == '{"version": 1}'


def test_deployment_backup_digest_failure_blocks_restore(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.mkdir()
    (source / "app.txt").write_text("version one", encoding="utf-8")
    controller = LocalDeploymentController(tmp_path / "deployments")
    controller.deploy(_profile(source))
    backup = controller.backup_current(
        "local-proof",
        seed_id="seed-proof",
        artifact_id="artifact-proof-1",
        backup_id="backup-1",
    )
    Path(backup.release_path, "app.txt").write_text("tampered", encoding="utf-8")

    with pytest.raises(DeploymentError, match="release digest"):
        controller.restore_backup("local-proof", "backup-1")
