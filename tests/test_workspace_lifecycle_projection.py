"""The workspace contract reads every durable Hardware Store lifecycle category."""

from __future__ import annotations

from pathlib import Path

from kernel.hardware_lifecycle import HardwareRecord
from kernel.hardware_migration import HardwareMigrationJournal, RollbackRecord
from kernel.hardware_promotion import PromotionPacket, PromotionPacketStore
from kernel.seedlab.approval import FileApprovalStore
from kernel.seedlab.deployment import DeploymentProfile, LocalDeploymentController
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.manifest_evidence import ManifestRunEvidence
from kernel.seedlab.workshop_services import CreatorWorkshopService
from kernel.seedlab.workspace_contract import build_workspace_contract


def test_workspace_contract_projects_durable_lifecycle_records(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    seed_id = "seed-lifecycle"
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Lifecycle Seed", "josh", "lifecycle projection", seed_id=seed_id
    )

    workshop = CreatorWorkshopService.durable(home / "workshop")
    workshop.create_draft("draft-1", seed_id, "josh", {"command": "inspect"})
    approvals = FileApprovalStore(home / "workshop" / "approvals")
    approvals.request(
        "approval-1",
        job_id="job-1",
        seed_id=seed_id,
        requested_by="josh",
        capability="component.activate",
        scope=seed_id,
        created_at="2026-08-05T12:00:00+00:00",
        expires_at="2026-08-05T13:00:00+00:00",
    )

    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "app.txt").write_text("healthy", encoding="utf-8")
    LocalDeploymentController(
        home / "deployments",
        clock=lambda: "2026-08-05T12:01:00+00:00",
        id_minter=iter(["deploy-1"]).__next__,
    ).deploy(DeploymentProfile("local-proof", seed_id, "artifact-1", str(artifact)))

    component = HardwareRecord(
        component_id="event-ledger",
        version="1.0.0",
        state="active",
        source="kernel/ledger.py",
        license="MIT",
        provenance="original",
        consumers=(seed_id,),
        history=("discovered", "validated", "approved", "installed", "active"),
    )
    rollback = RollbackRecord(
        rollback_id="rollback-1",
        migration_id="migration-1",
        component_id=component.component_id,
        seed_id=seed_id,
        from_version="1.0.0",
        to_version="2.0.0",
        backup_reference="backup-1",
        trigger="health-check",
        status="completed",
        health="healthy",
        operator_decision="approved",
        completed_at="2026-08-05T12:02:00+00:00",
    )
    HardwareMigrationJournal(home / "hardware").save_rollback(rollback)
    PromotionPacketStore(home / "hardware" / "promotions").save(
        PromotionPacket(
            packet_id="packet-1",
            component_id=component.component_id,
            version=component.version,
            artifact_digest="sha256:component",
            provenance_id="prov-component",
            license_decision="approved",
            sbom_reference="sbom-component",
            security_evidence="security-clean",
            accessibility_evidence="accessibility-clean",
            test_evidence="tests-passed",
            owner="team.seed-runtime",
            consumers=(seed_id,),
            human_reviewer="reviewer",
            operator_decision="approved",
        )
    )
    test_evidence = ManifestRunEvidence(
        evidence_id="evidence-1",
        manifest_id="manifest-1",
        manifest_digest="digest-1",
        seed_id=seed_id,
        job_id="job-1",
        event_id="event-1",
        status="succeeded",
        target_profile="python",
        required_components=(component.component_id,),
        created_at="2026-08-05T12:03:00+00:00",
    )

    contract = build_workspace_contract(
        seed_id,
        root=home,
        manifest_evidence=(test_evidence,),
        hardware_records=(component,),
    )
    evidence = next(
        package.payload
        for package in contract.packages
        if package.package == "Engineering.Evidence"
    )
    lifecycle = evidence["lifecycle"]

    assert lifecycle["catalog"]
    assert lifecycle["drafts"][0]["draft_id"] == "draft-1"
    assert lifecycle["drafts"][0]["seed_id"] == seed_id
    assert lifecycle["tests"] == [
        {
            "evidence_id": "evidence-1",
            "manifest_id": "manifest-1",
            "manifest_digest": "digest-1",
            "seed_id": seed_id,
            "job_id": "job-1",
            "event_id": "event-1",
            "status": "succeeded",
            "target_profile": "python",
            "required_components": [component.component_id],
            "created_at": "2026-08-05T12:03:00+00:00",
        }
    ]
    assert lifecycle["approvals"][0]["approval_id"] == "approval-1"
    assert lifecycle["activations"][0]["component_id"] == component.component_id
    assert lifecycle["health"][0]["run_id"] == "deploy-1"
    assert lifecycle["rollbacks"][0]["rollback_id"] == "rollback-1"
    assert lifecycle["promotions"][0]["packet_id"] == "packet-1"


def test_workspace_contract_filters_seed_scoped_lifecycle_records(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Lifecycle Seed", "josh", "lifecycle projection", seed_id="seed-one"
    )
    workshop = CreatorWorkshopService.durable(home / "workshop")
    workshop.create_draft("draft-other", "seed-two", "josh", {"command": "inspect"})
    FileApprovalStore(home / "workshop" / "approvals").request(
        "approval-other",
        job_id="job-other",
        seed_id="seed-two",
        requested_by="josh",
        capability="component.activate",
        scope="seed-two",
        created_at="2026-08-05T12:00:00+00:00",
        expires_at="2026-08-05T13:00:00+00:00",
    )

    evidence = ManifestRunEvidence(
        evidence_id="evidence-other",
        manifest_id="manifest-other",
        manifest_digest="digest-other",
        seed_id="seed-two",
        job_id="job-other",
        event_id="event-other",
        status="succeeded",
        target_profile="python",
        required_components=(),
        created_at="2026-08-05T12:03:00+00:00",
    )
    contract = build_workspace_contract(
        "seed-one", root=home, manifest_evidence=(evidence,), hardware_records=()
    )
    lifecycle = next(
        package.payload["lifecycle"]
        for package in contract.packages
        if package.package == "Engineering.Evidence"
    )
    assert lifecycle["drafts"] == []
    assert lifecycle["approvals"] == []
    assert lifecycle["tests"] == []
