"""Contract tests for the read-only Engineering.Evidence workspace package."""

from __future__ import annotations

from kernel.hardware_lifecycle import HardwareRecord
from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel
from kernel.seedlab.manifest_evidence import ManifestRunEvidence
from kernel.seedlab.workspace_gmcp import ENGINEERING_EVIDENCE_PACKAGE, workspace_packages


def test_workspace_projects_durable_evidence_and_hardware_state() -> None:
    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: "2026-08-05T12:00:00+00:00")
    seed = kernel.create_seed("Aethryn", "josh", "flagship Seed", seed_id="seed-aethryn")
    evidence = ManifestRunEvidence(
        evidence_id="evidence-aethryn-job-1",
        manifest_id="manifest-aethryn",
        manifest_digest="digest-1",
        seed_id=seed.identity.seed_id,
        job_id="job-1",
        event_id="evt-evidence-aethryn-job-1",
        status="succeeded",
        target_profile="python",
        required_components=("event-ledger",),
        created_at="2026-08-05T12:01:00+00:00",
    )
    hardware = HardwareRecord(
        component_id="event-ledger",
        version="1.0.0",
        state="active",
        source="builtin",
        license="Matrym Labs internal",
        provenance="codeforge",
        consumers=("seed-aethryn",),
        history=("discovered", "validated", "approved", "installed", "active"),
    )

    packages = workspace_packages(
        seed,
        manifest_evidence=(evidence,),
        hardware_records=(hardware,),
    )

    package, payload = packages[-1]
    assert package == ENGINEERING_EVIDENCE_PACKAGE
    assert payload["seed"] == "seed-aethryn"
    assert payload["manifest_runs"][0]["job_id"] == "job-1"
    assert payload["hardware"][0]["state"] == "active"
    assert payload["hardware"][0]["history"] == [
        "discovered",
        "validated",
        "approved",
        "installed",
        "active",
    ]
    assert payload["lifecycle"]["tests"][0]["job_id"] == "job-1"
    assert payload["lifecycle"]["activations"][0]["component_id"] == "event-ledger"
    assert payload["lifecycle"]["approvals"] == []


def test_workspace_projects_supplied_lifecycle_records_without_mutating_authority() -> None:
    kernel = SeedKernel(InMemorySeedStore())
    seed = kernel.create_seed("Forge", "josh", "engineering Seed", seed_id="seed-forge")
    payload = workspace_packages(
        seed,
        lifecycle_evidence={
            "drafts": ({"draft_id": "draft-1", "status": "review"},),
            "approvals": ({"approval_id": "approval-1", "status": "approved"},),
            "promotions": ({"packet_id": "packet-1", "status": "approved"},),
        },
    )[-1][1]

    assert payload["lifecycle"]["drafts"] == [{"draft_id": "draft-1", "status": "review"}]
    assert payload["lifecycle"]["approvals"] == [
        {"approval_id": "approval-1", "status": "approved"}
    ]
    assert payload["lifecycle"]["promotions"] == [{"packet_id": "packet-1", "status": "approved"}]


def test_workspace_does_not_project_evidence_for_another_seed() -> None:
    kernel = SeedKernel(InMemorySeedStore())
    seed = kernel.create_seed("Aethryn", "josh", "flagship Seed", seed_id="seed-aethryn")
    other = ManifestRunEvidence(
        evidence_id="evidence-other-job-1",
        manifest_id="manifest-other",
        manifest_digest="digest-other",
        seed_id="seed-other",
        job_id="job-other",
        event_id="evt-other",
        status="failed",
        target_profile="python",
        required_components=(),
        created_at="2026-08-05T12:01:00+00:00",
    )

    payload = workspace_packages(seed, manifest_evidence=(other,))[-1][1]
    assert payload["manifest_runs"] == []

    foreign_hardware = HardwareRecord(
        component_id="foreign-validator",
        version="1.0.0",
        state="active",
        source="builtin",
        license="Matrym Labs internal",
        provenance="codeforge",
        consumers=("seed-other",),
        history=("discovered", "validated", "approved", "installed", "active"),
    )
    foreign_payload = workspace_packages(seed, hardware_records=(foreign_hardware,))[-1][1]
    assert foreign_payload["hardware"] == []
    assert foreign_payload["lifecycle"]["activations"] == []
