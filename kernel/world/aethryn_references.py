"""CARD: aethryn_references -- cross-record reference resolution for WorldIR."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.world.aethryn_diagnostics import Diagnostic, DiagnosticReport, diagnostic
from kernel.world.aethryn_ir import WorldIR
from kernel.world.aethryn_schema import SchemaRegistry


def _field_value(payload: Mapping[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


def _reference_values(value: Any, collection: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if collection == "mapping_values":
        if not isinstance(value, Mapping):
            return ()
        return tuple(str(item) for item in value.values())
    if collection == "mapping_keys":
        if not isinstance(value, Mapping):
            return ()
        return tuple(str(item) for item in value)
    if collection == "list":
        if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
            return ()
        return tuple(str(item) for item in value)
    return (str(value),)


def resolve_references(ir: WorldIR, registry: SchemaRegistry) -> DiagnosticReport:
    """Resolve declared references and return actionable failures for missing targets."""
    findings: list[Diagnostic] = []
    for type_id, rows in ir.records.items():
        schema = registry.require(type_id)
        for record in rows.values():
            for reference in schema.reference_fields:
                values = _reference_values(
                    _field_value(record.payload, reference.field_path), reference.collection
                )
                target_types = tuple(reference.target_type.split("|"))
                known: set[str] = set()
                for target_type in target_types:
                    known.update(ir.record_ids(target_type))
                    known.update(ir.external_ids.get(target_type, frozenset()))
                for target_id in values:
                    if target_id in known:
                        continue
                    findings.append(
                        diagnostic(
                            "unresolved_reference",
                            (
                                f"{type_id}:{record.stable_id} references missing "
                                f"{reference.target_type}:{target_id}"
                            ),
                            subsystem="reference_resolution",
                            source_path=f"records.{type_id}",
                            record_id=record.stable_id,
                            field=reference.field_path,
                            violated_rule=(
                                "declared references must resolve to a normalized or explicitly "
                                "external record"
                            ),
                            authority_source="WorldIR schema registry",
                            suggested_correction=(
                                f"add {reference.target_type}:{target_id}, correct the field, "
                                "or declare an approved external id"
                            ),
                            related_records=(f"{reference.target_type}:{target_id}",),
                        )
                    )
    return DiagnosticReport(tuple(findings))
