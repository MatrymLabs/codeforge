from datetime import UTC, datetime, timedelta

import pytest

from kernel.hardware_activation import ActivationApproval, ActivationApprovalLedger
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.hardware_runtime import HardwareRuntimeController, HardwareRuntimeError
from kernel.permission_policy import PermissionDenied, PermissionPolicy, PermissionRule
from kernel.session_identity import SessionIdentity
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


def _identity(seed_id: str, principal: str = "operator") -> SessionIdentity:
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    return SessionIdentity(
        principal,
        "human",
        f"session-{principal}",
        seed_id,
        now - timedelta(minutes=1),
        now + timedelta(minutes=30),
        f"corr-{principal}",
        roles=frozenset({"operator"}),
        capabilities=frozenset({"component.activate", "component.disable", "component.restore"}),
    )


def _installed(registry: HardwareRegistry) -> None:
    registry.discover("validator")
    for state in ("validated", "approved", "installed"):
        registry.transition("validator", state)


def _controller(tmp_path, seed_id: str = "seed-a"):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    controller = HardwareRuntimeController(
        hardware, PluginRegistry(), seed_id=seed_id, consumer=seed_id
    )
    plugin = object()
    controller.register_provider(PluginInfo("validator"), lambda: plugin)
    return hardware, controller, plugin


def _approval(hardware: HardwareRegistry, seed_id: str = "seed-a") -> ActivationApproval:
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    return ActivationApproval(
        "approval-runtime",
        "validator",
        hardware.get("validator").version,
        seed_id,
        "reviewer",
        (now + timedelta(minutes=5)).isoformat(),
    )


def _policy() -> PermissionPolicy:
    return PermissionPolicy(
        tuple(
            PermissionRule(capability, scope="seed-a")
            for capability in (
                "component.activate",
                "component.disable",
                "component.restore",
            )
        )
    )


def test_controller_wires_approved_hardware_to_live_runtime_and_consumer(tmp_path):
    hardware, controller, plugin = _controller(tmp_path)
    controller.activate(
        "validator",
        approval=_approval(hardware),
        ledger=ActivationApprovalLedger(tmp_path / "approvals.json"),
        identity=_identity("seed-a"),
        policy=_policy(),
        now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC),
    )
    assert controller.runtime.get("validator") is plugin
    assert hardware.get("validator").state == "active"
    assert hardware.get("validator").consumers == ("seed-a",)


def test_controller_refuses_missing_provider_before_activation(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    controller = HardwareRuntimeController(
        hardware, PluginRegistry(), seed_id="seed-a", consumer="seed-a"
    )
    with pytest.raises(HardwareRuntimeError, match="no trusted runtime provider"):
        controller.activate(
            "validator",
            approval=_approval(hardware),
            ledger=ActivationApprovalLedger(tmp_path / "approvals.json"),
            identity=_identity("seed-a"),
            policy=_policy(),
            now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC),
        )
    assert hardware.get("validator").state == "installed"


def test_controller_enforces_seed_scoped_permission_and_separate_reviewer(tmp_path):
    hardware, controller, _plugin = _controller(tmp_path)
    with pytest.raises(PermissionDenied, match="no grant"):
        controller.activate(
            "validator",
            approval=_approval(hardware),
            ledger=ActivationApprovalLedger(tmp_path / "approvals.json"),
            identity=_identity("seed-a"),
            policy=PermissionPolicy(),
            now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC),
        )
    with pytest.raises(PermissionDenied, match="separate approval"):
        controller.activate(
            "validator",
            approval=ActivationApproval(
                "approval-self",
                "validator",
                hardware.get("validator").version,
                "seed-a",
                "operator",
                (datetime(2026, 8, 5, 18, 5, tzinfo=UTC)).isoformat(),
            ),
            ledger=ActivationApprovalLedger(tmp_path / "self-approvals.json"),
            identity=_identity("seed-a"),
            policy=_policy(),
            now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC),
        )


def test_controller_disable_and_remove_disconnect_runtime(tmp_path):
    hardware, controller, _plugin = _controller(tmp_path)
    controller.activate(
        "validator",
        approval=_approval(hardware),
        ledger=ActivationApprovalLedger(tmp_path / "approvals.json"),
        identity=_identity("seed-a"),
        policy=_policy(),
        now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC),
    )
    controller.remove(
        "validator",
        identity=_identity("seed-a"),
        policy=_policy(),
        now=datetime(2026, 8, 5, 18, 0, tzinfo=UTC),
    )
    assert controller.runtime.get("validator") is None
    assert hardware.get("validator").state == "disabled"
    assert hardware.get("validator").consumers == ()
