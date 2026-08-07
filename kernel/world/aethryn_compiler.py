"""CARD: aethryn_compiler -- offline deterministic packet compiler and package publisher."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from kernel.world.aethryn_delivery import (
    PACKAGE_SCHEMA_VERSION,
    cache_key,
    restore_cached_package,
    store_cached_package,
)
from kernel.world.aethryn_models import (
    GenerationManifest,
    Provenance,
    ValidationIssue,
    ValidationReport,
    ValidationVerdict,
    content_digest,
)
from kernel.world.aethryn_passes import run_foundation_pipeline
from kernel.world.aethryn_room_prose import (
    build_packet_presentations,
    similarity_report,
)
from kernel.world.aethryn_schema import default_schema_registry
from kernel.world.aethryn_validation import format_report, load_packet, validate_packet

DEFAULT_GENERATED_ROOT = (
    Path(__file__).resolve().parents[2] / "content" / "seeds" / "aethryn" / "generated"
)
DEFAULT_BATCH_ROOT = (
    Path(__file__).resolve().parents[2] / "content" / "seeds" / "aethryn" / "room_batches"
)
COMPILER_VERSION = "aethryn-compiler/1.1"


class CompilationError(ValueError):
    """A packet failed validation and therefore cannot become a package."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(format_report(report))


def _external_ids(root: Path | None) -> dict[str, frozenset[str]]:
    """Expose existing Seed room ids as explicit external references to the IR."""
    if root is None:
        root = Path(__file__).resolve().parents[2]
    from kernel.world.aethryn_validation import _all_room_labels

    return {"rooms": _all_room_labels(root)}


def _compatibility_external_ids(packet: Any, root: Path | None) -> dict[str, frozenset[str]]:
    """Expose legacy replacement and population references as an explicit adapter seam."""
    external = _external_ids(root)
    packet_room_ids = {str(row.get("id")) for row in packet.records.get("rooms", ())}
    replacement_targets = {
        str(destination)
        for row in packet.records.get("rooms", ())
        if row.get("replace")
        for destination in dict(row.get("exits", {})).values()
        if str(destination) not in packet_room_ids
    }
    if replacement_targets:
        external["rooms"] = frozenset(set(external.get("rooms", ())) | replacement_targets)
    packet_population_ids = {
        str(row.get("id")) for row in packet.records.get("population_profiles", ())
    }
    population_targets = {
        str(row.get("population_id"))
        for kind in ("spawn_pools", "roaming_routes", "migration_rules", "ambient_presence")
        for row in packet.records.get(kind, ())
        if row.get("population_id") and str(row.get("population_id")) not in packet_population_ids
    }
    if population_targets:
        external["population_profiles"] = frozenset(population_targets)
    packet_npc_ids = {str(row.get("id")) for row in packet.records.get("npcs", ())}
    crowd_targets = {
        str(npc_id)
        for row in packet.records.get("crowd_specs", ())
        for npc_id in row.get("representative_npcs", ())
        if str(npc_id) not in packet_npc_ids
    }
    if crowd_targets:
        external["npcs"] = frozenset(crowd_targets)
    return external


def _foundation_report(report: Any) -> ValidationReport:
    """Adapt foundation diagnostics to the stable compiler error surface."""
    issues = tuple(
        ValidationIssue(
            category=finding.subsystem,
            code=finding.code,
            path=finding.source_path,
            message=finding.message,
            authority=finding.authority_source,
            action=finding.suggested_correction,
            severity=finding.severity,
        )
        for finding in report.diagnostics.diagnostics
        if finding.severity == "error"
    )
    return ValidationReport(verdict="FAIL", issues=issues)


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _write_yaml(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(_plain(value), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _enriched_records(packet: Any) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for kind, rows in packet.records.items():
        compiled: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            source_ids = list(record.get("source_design_ids", packet.source_design_ids))
            provenance = {
                "source_design_ids": source_ids,
                "source_paths": list(
                    record.get(
                        "source_paths", packet.source_paths or ("content/seeds/aethryn/design",)
                    )
                ),
                "packet_id": packet.packet_id,
                "generation_seed": packet.generation_seed,
                "generator_name": packet.generator_name,
                "generator_version": packet.generator_version,
                "authority": record.get("authority", packet.canon_status),
                "note": record.get("provenance_note", ""),
            }
            record["source_design_ids"] = source_ids
            record["canon_status"] = str(record.get("canon_status", packet.canon_status))
            record["generation_seed"] = packet.generation_seed
            record["generator_name"] = packet.generator_name
            record["generator_version"] = packet.generator_version
            record["provenance"] = provenance
            record["content_digest"] = content_digest(record)
            compiled.append(record)
        records[kind] = compiled
    # A packet may opt into the structured material-culture catalog. Flatten it into ordinary
    # compiler records so materialization remains one package and runtime still consumes the
    # existing seed-shaped prototype/recipe/set paths.
    culture_anchors = records.get("material_culture", [])
    if culture_anchors:
        from kernel.world.material_culture import load_catalog

        for anchor in culture_anchors:
            catalog_path = Path(str(anchor.get("catalog_path", "")))
            if not catalog_path.is_absolute():
                catalog_path = Path(__file__).resolve().parents[2] / catalog_path
            catalog = load_catalog(catalog_path)
            sections = {
                "materials": catalog.materials,
                "item_families": catalog.families,
                "quality_profiles": catalog.qualities,
                # Source materials are emitted in the `materials` stream and are projected into
                # the legacy runtime registry directly from the catalog. Do not emit the same
                # stable id again as an item record: the runtime package intentionally rejects one
                # id with two differing records across kinds.
                "items": {
                    item_id: row
                    for item_id, row in catalog.prototypes.items()
                    if item_id not in catalog.materials
                },
                "crafting_stations": catalog.stations,
                "merchant_stock_profiles": catalog.merchant_stock,
                "loot_profiles": catalog.loot_profiles,
                "placements": catalog.placements,
                "equipment_sets": catalog.equipment_sets,
                "recipes": catalog.recipes,
            }
            for kind, section in sections.items():
                for stable_id, row in section.items():
                    enriched = dict(row)
                    enriched["id"] = stable_id
                    enriched.setdefault("display_name", stable_id.replace("_", " ").title())
                    enriched.setdefault(
                        "canon_status", catalog.metadata.get("canon_status", packet.canon_status)
                    )
                    enriched.setdefault(
                        "source_design_ids",
                        list(catalog.metadata.get("source_design_ids", packet.source_design_ids)),
                    )
                    records.setdefault(kind, []).append(enriched)
    presentation_records = {kind: tuple(rows) for kind, rows in records.items()}
    presentations = build_packet_presentations(packet, presentation_records)
    for room in records.get("rooms", []):
        room.update(
            {
                key: value
                for key, value in presentations[str(room["id"])].items()
                if key != "room_id"
            }
        )
        room["content_digest"] = content_digest(room)
    return records


def _room_batch(packet: Any, records: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    npcs_by_room: dict[str, list[str]] = {}
    npc_refs_by_room: dict[str, list[str]] = {}
    for npc in [*records.get("npcs", []), *records.get("creatures", [])]:
        location = str(npc.get("location", ""))
        if location:
            npcs_by_room.setdefault(location, []).append(
                str(npc.get("display_name", npc.get("name", npc["id"])))
            )
            npc_refs_by_room.setdefault(location, []).append(str(npc["id"]))
    objects_by_room: dict[str, list[str]] = {}
    object_refs_by_room: dict[str, list[str]] = {}
    for item in records.get("items", []):
        location = str(item.get("location", ""))
        if location:
            objects_by_room.setdefault(location, []).append(
                str(item.get("display_name", item.get("name", item["id"])))
            )
            object_refs_by_room.setdefault(location, []).append(str(item["id"]))
    population_refs_by_room: dict[str, list[str]] = {}
    for profile in records.get("population_profiles", []):
        for room in profile.get("candidate_rooms", profile.get("rooms", [])) or []:
            population_refs_by_room.setdefault(str(room), []).append(str(profile["id"]))
    crowd_refs_by_room: dict[str, list[str]] = {}
    for crowd in records.get("crowd_specs", []):
        for room in crowd.get("rooms", []) or []:
            crowd_refs_by_room.setdefault(str(room), []).append(str(crowd["id"]))
    evidence_refs_by_room: dict[str, list[str]] = {}
    for evidence in records.get("ambient_presence", []):
        evidence_rooms = evidence.get("rooms", []) or (
            [evidence.get("room")] if evidence.get("room") else []
        )
        for room in evidence_rooms:
            evidence_refs_by_room.setdefault(str(room), []).append(str(evidence["id"]))
    rooms: dict[str, dict[str, Any]] = {}
    for room in records.get("rooms", []):
        output: dict[str, Any] = {
            "name": str(room.get("display_name", room["id"])),
            "presentation_version": "aethryn-room-v1",
            "desc": str(
                room.get("long_description", room.get("description", room.get("desc", "")))
            ),
            "short_description": str(room.get("short_description", "")),
            "long_description": str(room.get("long_description", "")),
            "area_name": str(room.get("area_name", "")),
            "primary_purpose": list(room.get("primary_purpose", room.get("purpose", []))),
            "points_of_interest": list(room.get("points_of_interest", [])),
            "conditions": list(room.get("conditions", [])),
            "prose_status": str(room.get("prose_status", "GENERATED_LOCAL")),
            "prose_source": str(room.get("prose_source", "packet_description")),
            "canon_status": str(room.get("canon_status", packet.canon_status)),
            "parent_region": str(room.get("parent_region", packet.parent_region)),
            "parent_zone": str(room.get("parent_zone", packet.parent_zone)),
            "source_design_ids": list(room.get("source_design_ids", packet.source_design_ids)),
            "generation_seed": packet.generation_seed,
            "generator_name": packet.generator_name,
            "generator_version": packet.generator_version,
            "provenance": dict(room.get("provenance", {})),
            "content_digest": str(room.get("content_digest", "")),
            "room_type": str(room.get("room_type", "")),
            "tags": list(room.get("tags", [])),
            "exits": dict(room.get("exits", {})),
        }
        if room.get("replace"):
            output["replace"] = True
        if npcs_by_room.get(room["id"]):
            output["occupants"] = npcs_by_room[room["id"]]
            output["occupant_refs"] = npc_refs_by_room[room["id"]]
        if objects_by_room.get(room["id"]):
            output["objects"] = objects_by_room[room["id"]]
            output["object_refs"] = object_refs_by_room[room["id"]]
        if population_refs_by_room.get(room["id"]):
            output["population_refs"] = population_refs_by_room[room["id"]]
        if crowd_refs_by_room.get(room["id"]):
            output["crowd_refs"] = crowd_refs_by_room[room["id"]]
        if evidence_refs_by_room.get(room["id"]):
            output["ambient_evidence_refs"] = evidence_refs_by_room[room["id"]]
        rooms[str(room["id"])] = output
    return {
        "batch": {
            "id": packet.packet_id,
            "sequence": packet.batch_sequence,
            "status": "ready",
            "size": len(rooms),
            "final": True,
            "canon_status": packet.canon_status,
            "source_design_ids": list(packet.source_design_ids),
            "generation_seed": packet.generation_seed,
            "generator_name": packet.generator_name,
            "generator_version": packet.generator_version,
            "presentation_spec": "aethryn-room-v1",
        },
        "rooms": rooms,
    }


def _manifest(
    packet: Any,
    report: ValidationReport,
    records: Mapping[str, list[dict[str, Any]]],
    output_digest: str,
    build_cache_key: str = "",
) -> dict[str, Any]:
    provenance = Provenance(
        source_design_ids=tuple(packet.source_design_ids),
        source_paths=tuple(packet.source_paths or ("content/seeds/aethryn/design",)),
        packet_id=packet.packet_id,
        generation_seed=packet.generation_seed,
        generator_name=packet.generator_name,
        generator_version=packet.generator_version,
        authority=packet.canon_status,
        note="offline deterministic compiler output",
    )
    registry = default_schema_registry()
    schema_definitions = {definition.type_id: definition for definition in registry.definitions()}
    manifest = GenerationManifest(
        packet_id=packet.packet_id,
        generator_name=packet.generator_name,
        generator_version=packet.generator_version,
        generation_seed=packet.generation_seed,
        input_digest=report.input_digest,
        output_digest=output_digest,
        records={kind: len(rows) for kind, rows in records.items()},
        output_paths=tuple(packet.expected_output_paths),
        provenance=provenance,
        validation_verdict=report.verdict,
        package_schema_version=PACKAGE_SCHEMA_VERSION,
        compiler_version=COMPILER_VERSION,
        content_schema_versions={
            kind: schema_definitions[kind].schema_version
            for kind in records
            if kind in schema_definitions
        },
        migration_plan={
            "migration_required": False,
            "save_schema": "aethryn-save/1",
            "world_state_schema": "aethryn-world-state/1",
            "note": "package schema is compatible with the current compiler contract",
        },
        build_cache_key=build_cache_key,
    )
    return _plain(manifest)


def compile_packet(
    packet_path: Path,
    *,
    output_dir: Path | None = None,
    root: Path | None = None,
    cache_dir: Path | None = None,
) -> tuple[Path, GenerationManifest]:
    """Compile one packet into a staging package. No model or network boundary exists here."""
    packet = load_packet(packet_path)
    report = validate_packet(packet, root=root)
    if report.verdict == "FAIL":
        raise CompilationError(report)
    foundation = run_foundation_pipeline(
        packet,
        root=root,
        external_ids=_compatibility_external_ids(packet, root),
    )
    if foundation.verdict == "FAIL":
        raise CompilationError(_foundation_report(foundation))
    ir = foundation.ir
    if ir is None:
        raise CompilationError(
            ValidationReport(
                verdict="FAIL",
                issues=(
                    ValidationIssue(
                        category="pass_manager",
                        code="normalization_missing",
                        path="normalization",
                        message="foundation pipeline produced no WorldIR",
                        authority="compiler pass manager",
                        action="ensure the normalization pass is registered and returns WorldIR",
                    ),
                ),
            )
        )
    staging = output_dir or DEFAULT_GENERATED_ROOT / packet.packet_id
    build_key = cache_key(
        packet_payload=packet,
        source_digest=ir.source_digest,
        compiler_version=COMPILER_VERSION,
    )
    if staging.exists():
        shutil.rmtree(staging)
    if cache_dir is not None and restore_cached_package(cache_dir, build_key, staging):
        cached = yaml.safe_load((staging / "manifest.yaml").read_text(encoding="utf-8")) or {}
        return staging, GenerationManifest(
            packet_id=str(cached["packet_id"]),
            generator_name=str(cached["generator_name"]),
            generator_version=str(cached["generator_version"]),
            generation_seed=int(cached["generation_seed"]),
            input_digest=str(cached["input_digest"]),
            output_digest=str(cached["output_digest"]),
            records=dict(cached.get("records", {})),
            output_paths=tuple(cached.get("output_paths", ())),
            provenance=Provenance(**cached["provenance"]),
            validation_verdict=cast(ValidationVerdict, str(cached["validation_verdict"])),
            previous_package=str(cached.get("previous_package", "")),
            package_schema_version=str(
                cached.get("package_schema_version", PACKAGE_SCHEMA_VERSION)
            ),
            compiler_version=str(cached.get("compiler_version", COMPILER_VERSION)),
            content_schema_versions=dict(cached.get("content_schema_versions", {})),
            migration_plan=dict(cached.get("migration_plan", {})),
            build_cache_key=str(cached.get("build_cache_key", build_key)),
        )
    records = _enriched_records(packet)
    batch = _room_batch(packet, records)
    records_payload = _plain(records)
    state_payload = {
        str(row["key"]): {
            "initial_value": row.get("initial_value", ""),
            "reversible_values": list(row.get("reversible_values", [])),
            "visible_projection": row.get("visible_projection", ""),
            "persistence_scope": row.get("persistence_scope", ""),
            "room_id": row.get("room_id", ""),
            "actions": list(row.get("actions", [])),
        }
        for row in records.get("state_changes", [])
    }
    presentations = {str(room["id"]): room for room in records.get("rooms", [])}
    prose_similarity = similarity_report(presentations)
    output_digest = content_digest(
        {
            "batch": batch,
            "records": records_payload,
            "world_ir": ir.to_payload(),
            "world_state": state_payload,
            "prose_similarity": prose_similarity,
        }
    )
    manifest_data = _manifest(packet, report, records, output_digest, build_key)
    manifest = GenerationManifest(
        packet_id=manifest_data["packet_id"],
        generator_name=manifest_data["generator_name"],
        generator_version=manifest_data["generator_version"],
        generation_seed=manifest_data["generation_seed"],
        input_digest=manifest_data["input_digest"],
        output_digest=manifest_data["output_digest"],
        records=manifest_data["records"],
        output_paths=tuple(manifest_data["output_paths"]),
        provenance=Provenance(**manifest_data["provenance"]),
        validation_verdict=manifest_data["validation_verdict"],
        package_schema_version=manifest_data["package_schema_version"],
        compiler_version=manifest_data["compiler_version"],
        content_schema_versions=manifest_data["content_schema_versions"],
        migration_plan=manifest_data["migration_plan"],
        build_cache_key=manifest_data["build_cache_key"],
    )
    _write_yaml(staging / "room_batches" / f"{packet.packet_id}.yaml", batch)
    _write_yaml(staging / "records.yaml", records_payload)
    _write_yaml(staging / "world_ir.yaml", ir.to_payload())
    _write_yaml(staging / "world_state.yaml", state_payload)
    _write_yaml(staging / "room_prose_similarity.yaml", prose_similarity)
    _write_yaml(staging / "manifest.yaml", manifest_data)
    _write_yaml(staging / "validation_report.yaml", _plain(report))
    _write_yaml(staging / "provenance.yaml", manifest_data["provenance"])
    quest_ids = tuple(str(row.get("id")) for row in records.get("quests", []) if row.get("id"))
    if quest_ids or records.get("quest_pressures") or records.get("quest_arcs"):
        _write_yaml(
            staging / "quest_manifest.yaml",
            {
                "packet_id": packet.packet_id,
                "quest_ids": list(quest_ids),
                "pressure_ids": [str(row.get("id")) for row in records.get("quest_pressures", [])],
                "contract_ids": [
                    str(row.get("id")) for row in records.get("contract_templates", [])
                ],
                "arc_ids": [str(row.get("id")) for row in records.get("quest_arcs", [])],
                "public_event_ids": [
                    str(row.get("id")) for row in records.get("public_events", [])
                ],
                "digest": content_digest({"quests": quest_ids, "packet_id": packet.packet_id}),
                "generator_version": packet.generator_version,
            },
        )
    if cache_dir is not None:
        store_cached_package(cache_dir, build_key, staging)
    return staging, manifest


def publish_package(staging: Path, *, destination: Path | None = None) -> tuple[Path, Path | None]:
    """Publish a validated batch while retaining the previous artifact for restore."""
    batch_files = sorted((staging / "room_batches").glob("*.yaml"))
    if len(batch_files) != 1:
        raise CompilationError(
            ValidationReport(
                verdict="FAIL",
                issues=(),
            )
        )
    target_root = destination or DEFAULT_BATCH_ROOT
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / batch_files[0].name
    rollback: Path | None = None
    if target.exists():
        rollback = target_root.parent / ".aethryn_rollbacks" / target.name
        rollback.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, rollback)
    shutil.copy2(batch_files[0], target)
    return target, rollback


def restore_package(rollback: Path, *, destination: Path | None = None) -> Path:
    if not rollback.is_file():
        raise FileNotFoundError(f"rollback artifact not found: {rollback}")
    target_root = destination or DEFAULT_BATCH_ROOT
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / rollback.name
    shutil.copy2(rollback, target)
    return target


def explain_packet(packet_path: Path, *, root: Path | None = None) -> str:
    packet = load_packet(packet_path)
    report = validate_packet(packet, root=root)
    lines = [
        f"packet: {packet.packet_id}",
        f"target: {packet.target_type}",
        f"parent: {packet.parent_region} / {packet.parent_zone}",
        f"status: {packet.canon_status}",
        f"purpose: {packet.gameplay_purpose}",
        f"seed: {packet.generation_seed}",
        f"generator: {packet.generator_name} {packet.generator_version}",
        f"input_digest: {report.input_digest}",
        f"verdict: {report.verdict}",
    ]
    return "\n".join(lines) + ("\n\n" + format_report(report) if report.issues else "")


def provenance_for(staging: Path, stable_id: str) -> str:
    records_path = staging / "records.yaml"
    if not records_path.is_file():
        return f"provenance unavailable: package records are missing at {records_path}"
    raw = yaml.safe_load(records_path.read_text(encoding="utf-8")) or {}
    for kind, rows in raw.items():
        for row in rows or []:
            if isinstance(row, dict) and row.get("id") == stable_id:
                return yaml.safe_dump(
                    {"kind": kind, "record": row}, sort_keys=False, allow_unicode=True
                ).rstrip()
    return f"provenance not found: {stable_id}"


def diff_artifacts(first: Path, second: Path) -> str:
    first_text = first.read_text(encoding="utf-8")
    second_text = second.read_text(encoding="utf-8")
    first_digest = content_digest(first_text)
    second_digest = content_digest(second_text)
    if first_digest == second_digest:
        return f"identical\ndigest: {first_digest}"
    first_lines = first_text.splitlines()
    second_lines = second_text.splitlines()
    differences = []
    for index in range(max(len(first_lines), len(second_lines))):
        left = first_lines[index] if index < len(first_lines) else "<missing>"
        right = second_lines[index] if index < len(second_lines) else "<missing>"
        if left != right:
            differences.append(f"line {index + 1}: {left!r} != {right!r}")
            if len(differences) == 12:
                break
    return "\n".join(
        [
            "different",
            f"first_digest: {first_digest}",
            f"second_digest: {second_digest}",
            *differences,
        ]
    )
