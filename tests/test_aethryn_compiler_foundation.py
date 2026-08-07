"""Focused proof for the adapter-first Aethryn compiler foundation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from kernel.world.aethryn_ir import build_world_ir
from kernel.world.aethryn_passes import (
    PassContext,
    PassManager,
    PassManagerError,
    run_foundation_pipeline,
)
from kernel.world.aethryn_references import resolve_references
from kernel.world.aethryn_schema import (
    SchemaDefinition,
    SchemaRegistry,
    SchemaRegistryError,
    default_schema_registry,
)
from kernel.world.aethryn_validation import _all_room_labels, load_packet

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml"


def test_veridia_normalizes_through_world_ir_and_resolves_external_rooms() -> None:
    packet = load_packet(PACKET)
    room_ids = _all_room_labels(ROOT)
    result = run_foundation_pipeline(
        packet,
        root=ROOT,
        external_ids={
            "rooms": room_ids | frozenset({"greenhold_inn", "greenhold_store"}),
            "population_profiles": frozenset({"greenhold_boar_pressure"}),
            "npcs": frozenset({"greenhold_folk"}),
        },
    )

    assert result.verdict == "CLEAN"
    assert result.ir is not None
    assert result.ir.record_ids("rooms") == frozenset(row["id"] for row in packet.records["rooms"])
    assert result.ir.source_digest
    assert result.ir.to_payload()["records"]["rooms"]


def test_second_world_fixture_uses_normalization_and_reference_passes() -> None:
    packet = load_packet(PACKET)
    fixture = replace(
        packet,
        packet_id="second_world_fixture",
        parent_region="testland",
        parent_zone="testland_zone",
        records={
            "settlements": (
                {
                    "id": "stoneford",
                    "display_name": "Stoneford",
                    "parent_region": "testland",
                    "parent_zone": "testland_zone",
                },
            ),
            "rooms": (
                {
                    "id": "stoneford_gate",
                    "display_name": "Stoneford Gate",
                    "parent_region": "testland",
                    "parent_zone": "testland_zone",
                    "parent_settlement": "stoneford",
                    "exits": {"east": "stoneford_square"},
                },
                {
                    "id": "stoneford_square",
                    "display_name": "Stoneford Square",
                    "parent_region": "testland",
                    "parent_zone": "testland_zone",
                    "parent_settlement": "stoneford",
                    "exits": {"west": "stoneford_gate"},
                },
            ),
        },
    )
    result = run_foundation_pipeline(fixture, targets=("reference_resolution",))

    assert result.verdict == "CLEAN"
    assert result.ir is not None
    assert result.ir.world_id == "aethryn"
    assert result.ir.record_ids("settlements") == frozenset({"stoneford"})


def test_reference_failure_names_source_record_field_and_correction() -> None:
    packet = load_packet(PACKET)
    broken_rooms = [dict(row) for row in packet.records["rooms"]]
    broken_rooms[0]["exits"] = {"east": "missing_room"}
    broken = replace(packet, records={**packet.records, "rooms": tuple(broken_rooms)})
    registry = default_schema_registry()
    ir, normalization = build_world_ir(broken, registry)
    report = normalization.merge(resolve_references(ir, registry))

    issue = next(item for item in report.diagnostics if item.code == "unresolved_reference")
    assert issue.record_id == "greenhold"
    assert issue.field == "exits"
    assert "add rooms:missing_room" in issue.suggested_correction


def test_schema_registry_refuses_duplicate_contracts() -> None:
    registry = SchemaRegistry()
    definition = SchemaDefinition(
        type_id="fixture",
        schema_version="fixture/1",
        parser="fixture.parser",
        validator="fixture.validator",
        migration="identity",
        reference_fields=(),
        serialization_format="yaml",
        compiler_passes=("normalization",),
        runtime_adapter="fixture.runtime",
    )
    registry.register(definition)
    try:
        registry.register(definition)
    except SchemaRegistryError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate schema registration must fail")


def test_pass_manager_orders_dependencies_and_rejects_cycles() -> None:
    packet = load_packet(PACKET)
    registry = default_schema_registry()
    context = PassContext(packet=packet, root=ROOT, registry=registry)
    manager = PassManager()

    from kernel.world.aethryn_diagnostics import DiagnosticReport
    from kernel.world.aethryn_passes import CompilerPass, PassOutput

    def source(_context, _outputs):
        return PassOutput("source", None, DiagnosticReport())

    def target(_context, _outputs):
        return PassOutput("target", None, DiagnosticReport())

    manager.register(CompilerPass("source", (), source))
    manager.register(CompilerPass("target", ("source",), target))
    result = manager.execute(context, targets=("target",))
    assert [output.pass_name for output in result.outputs] == ["source", "target"]

    cyclic = PassManager()
    cyclic.register(CompilerPass("one", ("two",), source))
    cyclic.register(CompilerPass("two", ("one",), target))
    try:
        cyclic.ordered()
    except PassManagerError as exc:
        assert "dependency cycle" in str(exc)
    else:
        raise AssertionError("cyclic pass graph must fail")
