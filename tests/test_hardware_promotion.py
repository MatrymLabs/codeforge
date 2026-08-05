from pathlib import Path

import pytest

from kernel.hardware_lifecycle import HardwareRegistry
from kernel.hardware_promotion import (
    HardwarePromotionError,
    PromotionPacket,
    PromotionPacketStore,
    promote_hardware_component,
)
from kernel.permission_policy import PermissionContext, PermissionPolicy, PermissionRule


def _validated(registry: HardwareRegistry) -> None:
    registry.discover("validator")
    registry.transition("validator", "validated")


def _packet(registry: HardwareRegistry, **overrides: object) -> PromotionPacket:
    values: dict[str, object] = {
        "packet_id": "packet-validator-1",
        "component_id": "validator",
        "version": registry.get("validator").version,
        "artifact_digest": "sha256:artifact",
        "provenance_id": "prov:validator",
        "license_decision": "approved",
        "sbom_reference": "sbom://validator-1",
        "security_evidence": "security://validator-1",
        "accessibility_evidence": "accessibility://validator-1",
        "test_evidence": "tests://validator-1",
        "owner": "team.seed-runtime",
        "consumers": ("creator-workshop",),
        "human_reviewer": "reviewer-1",
        "operator_decision": "approved",
    }
    values.update(overrides)
    return PromotionPacket(**values)


def test_promotion_packet_is_durable_and_advances_only_validated_component(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _validated(registry)
    packets = PromotionPacketStore(tmp_path / "packets")
    packet = _packet(registry)

    promoted = promote_hardware_component(registry, packets, packet)

    assert promoted.state == "approved"
    assert packets.load(packet.packet_id) == packet
    assert [entry["action"] for entry in packets.audit_records()] == [
        "promotion_packet_stored",
        "promotion_authorized",
    ]


def test_promotion_requires_seedless_component_policy_when_supplied(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _validated(registry)
    packets = PromotionPacketStore(tmp_path / "packets")
    packet = _packet(registry)
    policy = PermissionPolicy(
        rules=(PermissionRule("hardware.promote", scope="component:validator"),)
    )
    permission = PermissionContext(
        "reviewer-1",
        capabilities=frozenset({"hardware.promote"}),
    )

    promoted = promote_hardware_component(
        registry,
        packets,
        packet,
        policy=policy,
        permission=permission,
    )

    assert promoted.state == "approved"
    assert packets.audit_records()[-1]["actor_id"] == "reviewer-1"


def test_promotion_audit_tampering_fails_loud(tmp_path: Path) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _validated(registry)
    packets = PromotionPacketStore(tmp_path / "packets")
    promote_hardware_component(registry, packets, _packet(registry))
    audit_path = packets.audit_path
    assert audit_path is not None
    tampered = audit_path.read_text(encoding="utf-8").replace(
        "promotion_authorized", "tampered"
    )
    audit_path.write_text(tampered, encoding="utf-8")

    with pytest.raises(HardwarePromotionError, match="cannot read promotion audit"):
        packets.audit_records()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("license_decision", "pending", "license decision"),
        ("security_evidence", "", "security_evidence"),
        ("automated_only", True, "automated evidence"),
        ("operator_decision", "pending", "operator decision"),
    ],
)
def test_scanner_or_incomplete_evidence_cannot_promote(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    registry = HardwareRegistry(tmp_path / "hardware.json")
    _validated(registry)
    with pytest.raises(HardwarePromotionError, match=message):
        promote_hardware_component(
            registry,
            PromotionPacketStore(tmp_path / "packets"),
            _packet(registry, **{field: value}),
        )
    assert registry.get("validator").state == "validated"
