from __future__ import annotations

from pathlib import Path

import pytest

from kernel.hardware_activation import activate_hardware_component
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.seedlab.event_bridge import SEED_EVENT_TOPIC
from kernel.seedlab.manifest_evidence import (
    FileManifestEvidenceStore,
    ManifestEvidenceError,
    SeedManifest,
    run_manifest_test,
)
from kernel.seedlab.workshop_services import CreatorWorkshopService
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry
from kernel.world import bus


def _manifest(root: Path, seed_id: str = "aethryn") -> SeedManifest:
    source = root / seed_id
    source.mkdir(parents=True)
    (source / "README.md").write_text("manifest slice\n", encoding="utf-8")
    return SeedManifest(
        manifest_id=f"manifest-{seed_id}",
        seed_id=seed_id,
        source_root=source,
        source_id=f"{seed_id}-source",
        source_license="Matrym Labs internal",
        target_profile="python",
        required_components=("event-ledger",),
    )


def _installed_hardware(root: Path) -> HardwareRegistry:
    registry = HardwareRegistry(root / "hardware.json")
    record = registry.discover("event-ledger")
    for state in ("validated", "approved", "installed"):
        record = registry.transition(record.component_id, state)
    assert record.state == "installed"
    return registry


def _activate(registry: HardwareRegistry) -> None:
    runtime: PluginRegistry[object] = PluginRegistry()
    activate_hardware_component(
        registry,
        "event-ledger",
        runtime,
        PluginInfo("event-ledger"),
        object(),
    )


def test_manifest_job_evidence_requires_explicit_hardware_activation(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    registry = _installed_hardware(tmp_path)
    service = CreatorWorkshopService.durable(tmp_path / "workshop")
    evidence = FileManifestEvidenceStore(tmp_path / "evidence")

    with pytest.raises(ManifestEvidenceError, match="explicit activation"):
        run_manifest_test(
            manifest,
            service,
            registry,
            evidence,
            actor_id="matrym",
        )
    assert service.jobs_for_seed("aethryn") == ()


def test_manifest_to_job_to_evidence_survives_restart(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEFORGE_AUDIT", str(tmp_path / "audit.jsonl"))
    bus.reset_bus()
    received: list[dict[str, object]] = []
    bus.get_bus().subscribe(SEED_EVENT_TOPIC, received.append)
    try:
        manifest = _manifest(tmp_path)
        registry = _installed_hardware(tmp_path)
        _activate(registry)
        service = CreatorWorkshopService.durable(tmp_path / "workshop")
        evidence_store = FileManifestEvidenceStore(tmp_path / "evidence")

        result = run_manifest_test(
            manifest,
            service,
            registry,
            evidence_store,
            actor_id="matrym",
        )

        assert result.manifest_id == manifest.manifest_id
        assert result.manifest_digest == manifest.digest()
        assert result.job_id.startswith("job-test-")
        assert result.status == "succeeded"
        assert result.required_components == ("event-ledger",)
        assert received[-1]["event_type"] == "manifest.test.completed"
        assert received[-1]["payload"]["job_id"] == result.job_id  # type: ignore[index]

        recovered_service = CreatorWorkshopService.durable(tmp_path / "workshop")
        recovered_evidence = FileManifestEvidenceStore(tmp_path / "evidence")
        assert recovered_service.jobs_for_seed("aethryn")[0].job_id == result.job_id
        assert recovered_evidence.get(result.evidence_id) == result
    finally:
        bus.reset_bus()


def test_same_manifest_job_evidence_contract_works_for_second_seed(tmp_path: Path) -> None:
    registry = _installed_hardware(tmp_path)
    _activate(registry)
    evidence_store = FileManifestEvidenceStore(tmp_path / "evidence")
    service = CreatorWorkshopService.durable(tmp_path / "workshop")

    first = run_manifest_test(
        _manifest(tmp_path, "aethryn"),
        service,
        registry,
        evidence_store,
        actor_id="matrym",
    )
    second = run_manifest_test(
        _manifest(tmp_path, "first-forge"),
        service,
        registry,
        evidence_store,
        actor_id="matrym",
    )

    assert first.status == second.status == "succeeded"
    assert first.seed_id == "aethryn"
    assert second.seed_id == "first-forge"
    assert first.manifest_digest != second.manifest_digest
    assert {item.seed_id for item in evidence_store.all_for_seed("aethryn")} == {"aethryn"}
    assert {item.seed_id for item in evidence_store.all_for_seed("first-forge")} == {"first-forge"}
