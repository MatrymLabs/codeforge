import multiprocessing as mp
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kernel.hardware_activation import (
    ActivationApproval,
    ActivationApprovalError,
    ActivationApprovalLedger,
    activate_hardware_component,
    activate_hardware_component_with_approval,
    disable_hardware_component,
)
from kernel.hardware_lifecycle import HardwareRegistry
from kernel.hardware_promotion import PromotionPacket, PromotionPacketStore
from kernel.permission_policy import PermissionContext, PermissionPolicy, PermissionRule
from kernel.shelf.plugin_registry import PluginInfo, PluginRegistry


def _consume_approval_in_child(path: str, result_queue) -> None:
    try:
        ActivationApprovalLedger(Path(path)).consume("approval-process")
    except ActivationApprovalError as exc:
        result_queue.put(f"error:{exc}")
    else:
        result_queue.put("ok")


def _installed(registry: HardwareRegistry) -> None:
    registry.discover("validator")
    for state in ("validated", "approved", "installed"):
        registry.transition("validator", state)


def test_explicit_activation_registers_the_trusted_object(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    runtime: PluginRegistry[object] = PluginRegistry()
    plugin = object()
    activate_hardware_component(
        hardware, "validator", runtime, PluginInfo("validator", capabilities=frozenset()), plugin
    )
    assert hardware.get("validator").state == "active"
    assert runtime.get("validator") is plugin


def test_activation_approval_consumption_is_cross_process_and_audited(tmp_path):
    path = tmp_path / "approval-ledger.json"
    context = mp.get_context("spawn")
    results = context.Queue()
    workers = [
        context.Process(target=_consume_approval_in_child, args=(str(path), results))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0

    outcomes = [results.get(timeout=2) for _ in workers]
    assert outcomes.count("ok") == 1
    assert sum(
        outcome.startswith("error:activation approval 'approval-process' was already used")
        for outcome in outcomes
    ) == 1
    ledger = ActivationApprovalLedger(path)
    assert ledger.audit_records()[0]["action"] == "activation_approval_consumed"


def test_discovery_and_install_never_activate_a_runtime_plugin(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    runtime: PluginRegistry[object] = PluginRegistry()
    # Reaching the installed state is not activation; no object is registered implicitly.
    assert hardware.get("validator").state == "installed"
    assert runtime.names() == []


def test_disable_disconnects_runtime_plugin_and_updates_governed_state(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    runtime: PluginRegistry[object] = PluginRegistry()
    activate_hardware_component(hardware, "validator", runtime, PluginInfo("validator"), object())
    disable_hardware_component(hardware, "validator", runtime)
    assert hardware.get("validator").state == "disabled"
    assert runtime.get("validator") is None


def test_governed_activation_binds_approval_to_version_seed_and_one_time_use(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    ledger = ActivationApprovalLedger(tmp_path / "approval-ledger.json")
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    approval = ActivationApproval(
        "approval-1",
        "validator",
        hardware.get("validator").version,
        "seed-a",
        "reviewer",
        (now + timedelta(minutes=5)).isoformat(),
    )
    activate_hardware_component_with_approval(
        hardware,
        "validator",
        PluginRegistry(),
        PluginInfo("validator"),
        object(),
        approval=approval,
        ledger=ledger,
        seed_id="seed-a",
        now=now,
    )
    assert hardware.get("validator").state == "active"
    assert ledger.audit_records()[0]["approval_id"] == "approval-1"

    second_hardware = HardwareRegistry(tmp_path / "hardware-2.json")
    _installed(second_hardware)
    with pytest.raises(ActivationApprovalError, match="already used"):
        activate_hardware_component_with_approval(
            second_hardware,
            "validator",
            PluginRegistry(),
            PluginInfo("validator"),
            object(),
            approval=approval,
            ledger=ledger,
            seed_id="seed-a",
            now=now,
        )


def test_governed_activation_rejects_expired_or_mismatched_approval(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    ledger = ActivationApprovalLedger(tmp_path / "approval-ledger.json")
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    expired = ActivationApproval(
        "approval-expired",
        "validator",
        hardware.get("validator").version,
        "seed-a",
        "reviewer",
        (now - timedelta(seconds=1)).isoformat(),
    )
    with pytest.raises(ActivationApprovalError, match="expired"):
        activate_hardware_component_with_approval(
            hardware,
            "validator",
            PluginRegistry(),
            PluginInfo("validator"),
            object(),
            approval=expired,
            ledger=ledger,
            seed_id="seed-a",
            now=now,
        )
    mismatched = ActivationApproval(
        "approval-mismatch",
        "validator",
        hardware.get("validator").version,
        "seed-other",
        "reviewer",
        (now + timedelta(minutes=5)).isoformat(),
    )
    with pytest.raises(ActivationApprovalError, match="does not match"):
        activate_hardware_component_with_approval(
            hardware,
            "validator",
            PluginRegistry(),
            PluginInfo("validator"),
            object(),
            approval=mismatched,
            ledger=ledger,
            seed_id="seed-a",
            now=now,
        )


def test_governed_activation_can_bind_approval_to_an_exact_artifact_digest(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    ledger = ActivationApprovalLedger(tmp_path / "approval-ledger.json")
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    approval = ActivationApproval(
        "approval-digest",
        "validator",
        hardware.get("validator").version,
        "seed-a",
        "reviewer",
        (now + timedelta(minutes=5)).isoformat(),
        "sha256:approved-bytes",
    )
    with pytest.raises(ActivationApprovalError, match="exact artifact digest"):
        activate_hardware_component_with_approval(
            hardware,
            "validator",
            PluginRegistry(),
            PluginInfo("validator"),
            object(),
            approval=approval,
            ledger=ledger,
            seed_id="seed-a",
            now=now,
            artifact_digest="sha256:tampered-bytes",
        )
    runtime: PluginRegistry[object] = PluginRegistry()
    activate_hardware_component_with_approval(
        hardware,
        "validator",
        runtime,
        PluginInfo("validator"),
        object(),
        approval=approval,
        ledger=ledger,
        seed_id="seed-a",
        now=now,
        artifact_digest="sha256:approved-bytes",
    )
    assert hardware.get("validator").state == "active"


def test_activation_boundary_can_require_and_apply_promotion_evidence(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    hardware.discover("validator")
    hardware.transition("validator", "validated")
    packets = PromotionPacketStore(tmp_path / "packets")
    record = hardware.get("validator")
    packet = PromotionPacket(
        packet_id="packet-activation",
        component_id="validator",
        version=record.version,
        artifact_digest="sha256:artifact",
        provenance_id="prov:validator",
        license_decision="approved",
        sbom_reference="sbom://validator",
        security_evidence="security://validator",
        accessibility_evidence="accessibility://validator",
        test_evidence="tests://validator",
        owner="team.seed-runtime",
        consumers=("creator-workshop",),
        human_reviewer="reviewer-1",
        operator_decision="approved",
    )
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    approval = ActivationApproval(
        "approval-promotion",
        "validator",
        record.version,
        "seed-a",
        "reviewer",
        (now + timedelta(minutes=5)).isoformat(),
        "sha256:artifact",
    )
    runtime: PluginRegistry[object] = PluginRegistry()
    activate_hardware_component_with_approval(
        hardware,
        "validator",
        runtime,
        PluginInfo("validator"),
        object(),
        approval=approval,
        ledger=ActivationApprovalLedger(tmp_path / "ledger.json"),
        seed_id="seed-a",
        now=now,
        artifact_digest="sha256:artifact",
        promotion_packet=packet,
        promotion_packets=packets,
    )
    assert hardware.get("validator").state == "active"
    assert packets.load(packet.packet_id) == packet


def test_activation_boundary_applies_seed_scoped_policy_before_consuming_approval(tmp_path):
    hardware = HardwareRegistry(tmp_path / "hardware.json")
    _installed(hardware)
    ledger = ActivationApprovalLedger(tmp_path / "approval-ledger.json")
    now = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)
    approval = ActivationApproval(
        "approval-policy",
        "validator",
        hardware.get("validator").version,
        "seed-a",
        "reviewer",
        (now + timedelta(minutes=5)).isoformat(),
    )
    with pytest.raises(ActivationApprovalError, match="authorization refused"):
        activate_hardware_component_with_approval(
            hardware,
            "validator",
            PluginRegistry(),
            PluginInfo("validator"),
            object(),
            approval=approval,
            ledger=ledger,
            seed_id="seed-a",
            now=now,
            policy=PermissionPolicy(),
            permission=PermissionContext("operator", capabilities=frozenset()),
        )
    assert hardware.get("validator").state == "installed"
    assert ledger.audit_records() == ()

    activate_hardware_component_with_approval(
        hardware,
        "validator",
        PluginRegistry(),
        PluginInfo("validator"),
        object(),
        approval=approval,
        ledger=ledger,
        seed_id="seed-a",
        now=now,
        policy=PermissionPolicy((PermissionRule("component.activate", scope="seed-a"),)),
        permission=PermissionContext(
            "operator", capabilities=frozenset({"component.activate"})
        ),
    )
    audit = ledger.audit_records()[0]
    assert audit["actor_id"] == "operator"
    assert audit["seed_id"] == "seed-a"
    assert audit["component_id"] == "validator"
