"""CARD: aethryn_ir -- normalized, provenance-preserving Aethryn WorldIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.world.aethryn_diagnostics import Diagnostic, DiagnosticReport, diagnostic
from kernel.world.aethryn_models import GenerationPacket, content_digest
from kernel.world.aethryn_schema import SchemaRegistry, SchemaRegistryError

AUTHORITY_RANK = {
    "GENERATED_LOCAL": 1,
    "AUTHORED_LOCAL": 2,
    "CANON_WORKING": 3,
    "CANON_LOCKED": 4,
    "RUMOR": 1,
}


@dataclass(frozen=True, slots=True)
class WorldIRRecord:
    """One normalized record with its schema, authority, and source payload."""

    type_id: str
    stable_id: str
    schema_version: str
    authority: str
    source_design_ids: tuple[str, ...]
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WorldIR:
    """The shared compiler representation for one world profile."""

    world_id: str
    profile_id: str
    records: dict[str, dict[str, WorldIRRecord]]
    capabilities: frozenset[str]
    external_ids: dict[str, frozenset[str]]
    source_digest: str

    def record_ids(self, type_id: str) -> frozenset[str]:
        """Return stable ids for one type."""
        return frozenset(self.records.get(type_id, {}))

    def to_payload(self) -> dict[str, Any]:
        """Serialize the IR into deterministic YAML-compatible data."""
        return {
            "world_id": self.world_id,
            "profile_id": self.profile_id,
            "capabilities": sorted(self.capabilities),
            "external_ids": {
                key: sorted(values) for key, values in sorted(self.external_ids.items())
            },
            "source_digest": self.source_digest,
            "records": {
                type_id: [
                    {
                        "id": record.stable_id,
                        "schema_version": record.schema_version,
                        "canon_status": record.authority,
                        "source_design_ids": list(record.source_design_ids),
                        "payload": record.payload,
                    }
                    for record in sorted(rows.values(), key=lambda item: item.stable_id)
                ]
                for type_id, rows in sorted(self.records.items())
            },
        }


def build_world_ir(
    packet: GenerationPacket,
    registry: SchemaRegistry,
    *,
    external_ids: dict[str, frozenset[str]] | None = None,
) -> tuple[WorldIR, DiagnosticReport]:
    """Normalize packet records while refusing ambiguous type and id contracts."""
    findings: list[Diagnostic] = []
    normalized: dict[str, dict[str, WorldIRRecord]] = {}
    packet_external = {
        "regions": frozenset({packet.parent_region}),
        "zones": frozenset({packet.parent_zone}),
    }
    for type_id, rows in packet.records.items():
        try:
            schema = registry.require(type_id)
        except SchemaRegistryError as exc:
            findings.append(
                diagnostic(
                    "schema_missing",
                    str(exc),
                    subsystem="normalization",
                    record_id=type_id,
                    violated_rule="every content type must be registered",
                    authority_source="compiler schema registry",
                    suggested_correction="register the type before compiling the packet",
                )
            )
            continue
        bucket = normalized.setdefault(type_id, {})
        for index, raw in enumerate(rows):
            stable_id = str(raw.get("id", "")).strip()
            source_path = f"packet.records.{type_id}[{index}]"
            if not stable_id:
                findings.append(
                    diagnostic(
                        "stable_id_missing",
                        "record has no stable id",
                        subsystem="normalization",
                        source_path=source_path,
                        violated_rule="every normalized record needs a stable id",
                        authority_source="WorldIR contract",
                        suggested_correction="add a permanent lowercase_snake_case id",
                    )
                )
                continue
            authority = str(raw.get("canon_status", packet.canon_status))
            record = WorldIRRecord(
                type_id=type_id,
                stable_id=stable_id,
                schema_version=schema.schema_version,
                authority=authority,
                source_design_ids=tuple(
                    str(item) for item in raw.get("source_design_ids", packet.source_design_ids)
                ),
                payload=dict(raw),
            )
            previous = bucket.get(stable_id)
            if previous is not None:
                if previous.payload == record.payload:
                    findings.append(
                        diagnostic(
                            "duplicate_identical_record",
                            "identical record appears more than once",
                            subsystem="normalization",
                            source_path=source_path,
                            record_id=stable_id,
                            violated_rule="stable ids are unique within a content type",
                            authority_source="WorldIR contract",
                            suggested_correction="remove the duplicate source record",
                            severity="warning",
                        )
                    )
                else:
                    findings.append(
                        diagnostic(
                            "duplicate_conflicting_record",
                            "conflicting records share one stable id",
                            subsystem="normalization",
                            source_path=source_path,
                            record_id=stable_id,
                            violated_rule="source precedence must not silently overwrite content",
                            authority_source=(
                                "CANON_LOCKED > CANON_WORKING > AUTHORED_LOCAL > GENERATED_LOCAL"
                            ),
                            suggested_correction=(
                                "merge the source deliberately or assign a new stable id"
                            ),
                            related_records=(f"{type_id}:{stable_id}",),
                        )
                    )
                    if AUTHORITY_RANK.get(record.authority, 0) > AUTHORITY_RANK.get(
                        previous.authority, 0
                    ):
                        bucket[stable_id] = record
                continue
            bucket[stable_id] = record
    merged_external = {key: frozenset(values) for key, values in (external_ids or {}).items()}
    for key, values in packet_external.items():
        merged_external[key] = frozenset(set(merged_external.get(key, ())) | set(values))
    ir = WorldIR(
        world_id="aethryn",
        profile_id="aethryn",
        records=normalized,
        capabilities=frozenset({"canon", "topology", "prose", "provenance"}),
        external_ids=merged_external,
        source_digest=content_digest({"packet_id": packet.packet_id, "records": packet.records}),
    )
    return ir, DiagnosticReport(tuple(findings))
