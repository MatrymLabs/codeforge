from datetime import UTC, datetime, timedelta
from pathlib import Path

from kernel.hardware_activation import (
    ActivationApproval,
    ActivationApprovalLedger,
    activate_hardware_component_with_approval,
    remove_hardware_component,
    restore_active_hardware_component,
)
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


def _active(path: Path, seed_id: str, ledger: ActivationApprovalLedger) -> HardwareRegistry:
    registry = HardwareRegistry(path)
    registry.discover("validator")
    for state in ("validated", "approved", "installed"):
        registry.transition("validator", state)
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    approval = ActivationApproval(
        f"approval-{seed_id}",
        "validator",
        registry.get("validator").version,
        seed_id,
        "reviewer-1",
        (now + timedelta(minutes=5)).isoformat(),
    )
    activate_hardware_component_with_approval(
        registry,
        "validator",
        PluginRegistry(),
        PluginInfo("validator"),
        object(),
        approval=approval,
        ledger=ledger,
        seed_id=seed_id,
        now=now,
    )
    return registry


def test_one_hardware_component_survives_two_seed_restarts_independently(tmp_path: Path) -> None:
    ledger = ActivationApprovalLedger(tmp_path / "approvals.json")
    aethryn = _active(tmp_path / "aethryn-hardware.json", "Aethryn", ledger)
    forge = _active(tmp_path / "first-forge-hardware.json", "first-forge", ledger)
    aethryn.register_consumer("validator", "Aethryn")
    forge.register_consumer("validator", "first-forge")

    aethryn_runtime: PluginRegistry[object] = PluginRegistry()
    forge_runtime: PluginRegistry[object] = PluginRegistry()
    restore_active_hardware_component(
        HardwareRegistry(tmp_path / "aethryn-hardware.json"),
        "validator",
        aethryn_runtime,
        PluginInfo("validator"),
        object(),
    )
    restore_active_hardware_component(
        HardwareRegistry(tmp_path / "first-forge-hardware.json"),
        "validator",
        forge_runtime,
        PluginInfo("validator"),
        object(),
    )

    remove_hardware_component(aethryn, "validator", aethryn_runtime, consumer="Aethryn")

    assert aethryn.get("validator").state == "disabled"
    assert aethryn.get("validator").consumers == ()
    assert (
        HardwareRegistry(tmp_path / "first-forge-hardware.json").get("validator").state == "active"
    )
    assert forge.get("validator").state == "active"
    assert aethryn_runtime.get("validator") is None
    assert forge_runtime.names() == ["validator"]
    assert forge.get("validator").consumers == ("first-forge",)
