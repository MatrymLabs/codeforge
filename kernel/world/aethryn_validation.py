"""CARD: aethryn_validation -- actionable canon, graph, system, and packet gates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

from kernel.world import canon, worldgraph
from kernel.world.aethryn_models import (
    GenerationPacket,
    ValidationIssue,
    ValidationReport,
    ValidationVerdict,
    content_digest,
)
from kernel.world.aethryn_population import validate_population_records
from kernel.world.aethryn_quests import validate_quest_records
from kernel.world.aethryn_room_prose import (
    build_packet_presentations,
    similarity_report,
    validate_presentations,
)
from kernel.world.seed import SeedError, _UniqueKeyLoader

VALID_STATUSES = {"CANON_LOCKED", "CANON_WORKING", "AUTHORED_LOCAL", "GENERATED_LOCAL", "RUMOR"}
ROOM_PURPOSES = {
    "traversal",
    "social",
    "civic",
    "economic",
    "ecological",
    "encounter",
    "resource",
    "landmark",
    "narrative",
    "threshold",
    "puzzle",
    "recovery",
    "service",
}
VALID_DIRECTIONS = {"north", "south", "east", "west", "up", "down", "in", "out", "enter"}
OPEN_QUESTION_TERMS = (
    "whether the gods' fear was justified",
    "whether netharion survived",
    "whether netharion was benevolent",
    "whether all gods supported",
    "whether some gods still monitor",
    "whether the old civilization was about to damage reality",
    "whether the gods acted to preserve",
)


def _issue(
    issues: list[ValidationIssue],
    category: str,
    code: str,
    path: str,
    message: str,
    authority: str,
    action: str,
    *,
    severity: str = "error",
) -> None:
    issues.append(
        ValidationIssue(
            category=category,
            code=code,
            path=path,
            message=message,
            authority=authority,
            action=action,
            severity=severity,
        )
    )


def load_packet(path: Path) -> GenerationPacket:
    """Load a packet and fail with a path-specific corrective error."""
    if not path.is_file():
        raise SeedError(
            f"generation packet {path} not found; create the packet at the expected path"
        )
    raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(raw, dict):
        raise SeedError(f"generation packet {path}: root must be a mapping; add packet fields")
    return packet_from_mapping(raw, path=str(path))


def _required(raw: Mapping[str, Any], name: str, path: str) -> Any:
    value = raw.get(name)
    if value is None or value == "" or value == [] or value == {}:
        raise SeedError(
            f"generation packet {path}: missing required field '{name}'; add it before compile"
        )
    return value


def _text_list(value: Any, name: str, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(entry, str) and entry.strip() for entry in value
    ):
        raise SeedError(f"generation packet {path}: '{name}' must be a non-empty list of text")
    return tuple(value)


def packet_from_mapping(raw: Mapping[str, Any], *, path: str = "packet") -> GenerationPacket:
    required = (
        "packet_id",
        "target_type",
        "parent_region",
        "parent_zone",
        "canon_status",
        "world_purpose",
        "gameplay_purpose",
        "narrative_purpose",
        "inherited_constraints",
        "threat_range",
        "geography_profile",
        "climate_profile",
        "architecture_profile",
        "cultural_profile",
        "economy_profile",
        "ecology_profile",
        "required_connections",
        "required_content_counts",
        "state_scope",
        "forbidden_content",
        "generation_seed",
        "expected_output_paths",
        "generator_name",
        "generator_version",
        "source_design_ids",
        "records",
    )
    for name in required:
        _required(raw, name, path)
    status = raw["canon_status"]
    if status not in VALID_STATUSES:
        raise SeedError(
            f"generation packet {path}: canon_status {status!r} is invalid; "
            f"use one of {sorted(VALID_STATUSES)}"
        )
    threat = raw["threat_range"]
    if (
        not isinstance(threat, list)
        or len(threat) != 2
        or not all(isinstance(n, int) for n in threat)
    ):
        raise SeedError(
            f"generation packet {path}: threat_range must be [minimum, maximum] integers"
        )
    mappings = (
        "geography_profile",
        "climate_profile",
        "architecture_profile",
        "cultural_profile",
        "economy_profile",
        "ecology_profile",
        "required_content_counts",
        "records",
    )
    for name in mappings:
        if not isinstance(raw[name], dict):
            raise SeedError(f"generation packet {path}: '{name}' must be a mapping")
    counts: dict[str, int] = {}
    for key, value in raw["required_content_counts"].items():
        if not isinstance(value, int) or value < 0:
            raise SeedError(
                f"generation packet {path}: required_content_counts.{key} must be "
                "a non-negative integer"
            )
        counts[str(key)] = value
    records: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for kind, values in raw["records"].items():
        if not isinstance(values, list) or not all(isinstance(value, dict) for value in values):
            raise SeedError(f"generation packet {path}: records.{kind} must be a list of mappings")
        records[str(kind)] = tuple(values)
    return GenerationPacket(
        packet_id=str(raw["packet_id"]),
        target_type=str(raw["target_type"]),
        parent_region=str(raw["parent_region"]),
        parent_zone=str(raw["parent_zone"]),
        canon_status=status,
        world_purpose=str(raw["world_purpose"]),
        gameplay_purpose=str(raw["gameplay_purpose"]),
        narrative_purpose=str(raw["narrative_purpose"]),
        inherited_constraints=_text_list(
            raw["inherited_constraints"], "inherited_constraints", path
        ),
        threat_range=(int(threat[0]), int(threat[1])),
        geography_profile=raw["geography_profile"],
        climate_profile=raw["climate_profile"],
        architecture_profile=raw["architecture_profile"],
        cultural_profile=raw["cultural_profile"],
        economy_profile=raw["economy_profile"],
        ecology_profile=raw["ecology_profile"],
        required_connections=_text_list(raw["required_connections"], "required_connections", path),
        required_content_counts=counts,
        state_scope=str(raw["state_scope"]),
        forbidden_content=_text_list(raw["forbidden_content"], "forbidden_content", path),
        generation_seed=int(raw["generation_seed"]),
        expected_output_paths=_text_list(
            raw["expected_output_paths"], "expected_output_paths", path
        ),
        generator_name=str(raw["generator_name"]),
        generator_version=str(raw["generator_version"]),
        source_design_ids=_text_list(raw["source_design_ids"], "source_design_ids", path),
        records=records,
        authorization=str(raw.get("authorization", "")),
        batch_sequence=int(raw.get("batch_sequence", 1)),
        source_paths=_text_list(
            raw.get("source_paths", ["content/seeds/aethryn/design"]), "source_paths", path
        ),
    )


def _canon_region(region_id: str) -> dict[str, Any] | None:
    return next((row for row in canon.regions() if row["id"] == region_id), None)


@lru_cache(maxsize=4)
def _all_room_labels(root: Path) -> frozenset[str]:
    seed_root = root / "content" / "seeds" / "aethryn"
    labels: set[str] = set()
    paths = [seed_root / "rooms.yaml", *sorted((seed_root / "room_batches").glob("*.yaml"))]
    for path in paths:
        if not path.is_file():
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if path.parent.name == "room_batches":
            rows = raw.get("rooms", {}) if isinstance(raw, dict) else {}
            if isinstance(rows, dict):
                labels.update(rows)
        elif isinstance(raw, dict):
            labels.update(raw)
    for path in sorted((seed_root / "authored").glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict) and isinstance(raw.get("rooms"), dict):
            labels.update(raw["rooms"])
    return frozenset(labels)


def _record_ids(records: Mapping[str, tuple[Mapping[str, Any], ...]], kind: str) -> set[str]:
    return {str(row.get("id", "")) for row in records.get(kind, ()) if row.get("id")}


def _record_common(
    issues: list[ValidationIssue],
    packet: GenerationPacket,
    kind: str,
    row: Mapping[str, Any],
    index: int,
) -> None:
    path = f"records.{kind}[{index}]"
    stable_id = row.get("id")
    if not isinstance(stable_id, str) or not stable_id.strip():
        _issue(
            issues,
            "PROVENANCE",
            "missing_id",
            path,
            "generated record has no stable id",
            "packet contract",
            "add a permanent lowercase_snake_case id",
        )
    display_name = row.get("display_name", row.get("name"))
    if not isinstance(display_name, str) or not display_name.strip():
        _issue(
            issues,
            "PROVENANCE",
            "missing_display_name",
            path,
            "generated record has no display name",
            "packet contract",
            "add display_name or name",
        )
    status = row.get("canon_status", packet.canon_status)
    if status not in VALID_STATUSES:
        _issue(
            issues,
            "CANON",
            "invalid_status",
            f"{path}.canon_status",
            f"status {status!r} is not on the authority ladder",
            "canon.yaml",
            "use a declared canon status",
        )
    if status in {"CANON_LOCKED", "CANON_WORKING"} and not packet.authorization:
        _issue(
            issues,
            "CANON",
            "unauthorized_promotion",
            f"{path}.canon_status",
            f"record requests {status} without authorization",
            "canon.yaml",
            "use AUTHORED_LOCAL or GENERATED_LOCAL, or supply explicit human authorization",
        )
    source_ids = row.get("source_design_ids", packet.source_design_ids)
    if not isinstance(source_ids, list) or not source_ids:
        _issue(
            issues,
            "PROVENANCE",
            "missing_source_design",
            f"{path}.source_design_ids",
            "record has no source design id",
            "packet contract",
            "inherit or declare source_design_ids",
        )


def validate_packet(packet: GenerationPacket, *, root: Path | None = None) -> ValidationReport:
    """Validate a packet and return actionable findings rather than raising on content defects."""
    repo = root or Path(__file__).resolve().parents[2]
    issues: list[ValidationIssue] = []
    if packet.packet_id != packet.packet_id.casefold() or any(
        char not in "abcdefghijklmnopqrstuvwxyz0123456789_" for char in packet.packet_id
    ):
        _issue(
            issues,
            "PROVENANCE",
            "unstable_packet_id",
            "packet_id",
            f"packet id {packet.packet_id!r} is not lowercase_snake_case",
            "packet contract",
            "rename the packet before publication",
        )
    region = _canon_region(packet.parent_region)
    if region is None:
        _issue(
            issues,
            "CANON",
            "unknown_region",
            "parent_region",
            f"region {packet.parent_region!r} is not canon-locked",
            "canon.yaml",
            "use one of the fourteen canon region ids",
        )
    elif (
        packet.threat_range[0] < region["threat_min"]
        or packet.threat_range[1] > region["threat_max"]
    ):
        _issue(
            issues,
            "CANON",
            "threat_drift",
            "threat_range",
            f"packet band {packet.threat_range} exceeds {packet.parent_region} band "
            f"{region['threat_min']}-{region['threat_max']}",
            "canon.yaml",
            "keep the packet threat range inside the locked region band",
        )
    if packet.canon_status in {"CANON_LOCKED", "CANON_WORKING"} and not packet.authorization:
        _issue(
            issues,
            "CANON",
            "packet_promotion",
            "canon_status",
            f"packet requests {packet.canon_status} without explicit authorization",
            "canon.yaml",
            "use GENERATED_LOCAL or AUTHORED_LOCAL until a human approves promotion",
        )
    if packet.generation_seed < 0:
        _issue(
            issues,
            "DETERMINISM",
            "negative_seed",
            "generation_seed",
            "generation seed cannot be negative",
            "packet contract",
            "supply a stable non-negative seed",
        )
    if packet.batch_sequence < 1:
        _issue(
            issues,
            "PACKET",
            "invalid_batch_sequence",
            "batch_sequence",
            "batch sequence must be positive",
            "room batch contract",
            "assign a unique positive sequence before publication",
        )
    if not packet.generator_name or not packet.generator_version:
        _issue(
            issues,
            "DETERMINISM",
            "missing_generator_identity",
            "generator_name",
            "generator identity is incomplete",
            "packet contract",
            "record both generator name and version",
        )
    if not packet.state_scope:
        _issue(
            issues,
            "PROVENANCE",
            "missing_state_scope",
            "state_scope",
            "packet has no state scope",
            "packet contract",
            "declare where reversible state persists",
        )

    room_rows = packet.records.get("rooms", ())
    room_ids = _record_ids(packet.records, "rooms")
    known_rooms = _all_room_labels(repo) | room_ids
    duplicate_ids: set[str] = set()
    seen: set[str] = set()
    for kind, rows in packet.records.items():
        for index, row in enumerate(rows):
            stable_id = str(row.get("id", ""))
            if stable_id in seen and stable_id:
                duplicate_ids.add(stable_id)
            seen.add(stable_id)
            _record_common(issues, packet, kind, row, index)
    for stable_id in sorted(duplicate_ids):
        _issue(
            issues,
            "HIERARCHY",
            "duplicate_id",
            "records",
            f"record id {stable_id!r} appears more than once in the packet",
            "packet contract",
            "assign one permanent id to one record",
        )

    for index, room in enumerate(room_rows):
        path = f"records.rooms[{index}]"
        parents = [room.get("parent_settlement"), room.get("parent_wilderness")]
        if not any(isinstance(parent, str) and parent for parent in parents):
            _issue(
                issues,
                "HIERARCHY",
                "orphan_room",
                path,
                "room has no settlement or wilderness parent",
                "world hierarchy",
                "set parent_settlement or parent_wilderness",
            )
        purpose = room.get("purpose", [])
        if not isinstance(purpose, list) or not set(purpose) & ROOM_PURPOSES:
            _issue(
                issues,
                "ROOM_PURPOSE",
                "filler_room",
                f"{path}.purpose",
                "room has no recognized primary purpose",
                "generation contract",
                f"choose at least one of {sorted(ROOM_PURPOSES)}",
            )
        description = room.get("description", room.get("desc", ""))
        if not isinstance(description, str) or len(description.split()) < 20:
            _issue(
                issues,
                "ROOM_PURPOSE",
                "thin_description",
                f"{path}.description",
                "room description is too thin to establish place and function",
                "room batch contract",
                "write at least 20 words with a visible local purpose",
            )
        exits = room.get("exits", {})
        if not isinstance(exits, dict):
            _issue(
                issues,
                "GEOGRAPHY",
                "invalid_exits",
                f"{path}.exits",
                "room exits must be a direction-to-id mapping",
                "CodeForge seed contract",
                "use a mapping of valid directions to room ids",
            )
            continue
        for direction, destination in exits.items():
            named_exit = isinstance(direction, str) and re.fullmatch(r"[a-z][a-z0-9_]*", direction)
            if direction not in VALID_DIRECTIONS and not named_exit:
                _issue(
                    issues,
                    "GEOGRAPHY",
                    "invalid_direction",
                    f"{path}.exits.{direction}",
                    f"direction {direction!r} is not supported",
                    "CodeForge seed contract",
                    f"use one of {sorted(VALID_DIRECTIONS)}",
                )
            inherited_existing_exit = bool(room.get("replace")) and destination not in room_ids
            if destination not in known_rooms and not inherited_existing_exit:
                _issue(
                    issues,
                    "GEOGRAPHY",
                    "dangling_exit",
                    f"{path}.exits.{direction}",
                    f"exit targets unknown room {destination!r}",
                    "world graph",
                    "add the target record or correct the exit",
                )
            if destination in room_ids:
                target = next(row for row in room_rows if row.get("id") == destination)
                reverse = any(value == room.get("id") for value in target.get("exits", {}).values())
                if not reverse:
                    _issue(
                        issues,
                        "GEOGRAPHY",
                        "non_reciprocal_exit",
                        f"{path}.exits.{direction}",
                        f"exit to {destination!r} has no reciprocal exit",
                        "world graph",
                        "add a reciprocal exit or mark the route as an explicitly one-way system",
                    )

    for index, settlement in enumerate(packet.records.get("settlements", ())):
        path = f"records.settlements[{index}]"
        required = (
            "population_band",
            "government",
            "food_sources",
            "water_source",
            "fuel_source",
            "labor_base",
            "waste_handling",
            "economy",
            "architecture",
            "culture",
            "services",
            "external_connections",
            "active_conflicts",
            "daily_rhythm",
        )
        for field_name in required:
            value = settlement.get(field_name)
            if value is None or value == "" or value == []:
                _issue(
                    issues,
                    "SETTLEMENT",
                    "missing_system",
                    f"{path}.{field_name}",
                    f"settlement is missing {field_name}",
                    "settlement system contract",
                    "describe the system or mark it not_yet_modeled",
                )

    for index, creature in enumerate(packet.records.get("creatures", ())):
        path = f"records.creatures[{index}]"
        creature_required = (
            "habitat",
            "diet_or_energy_source",
            "predators",
            "prey_or_resource_pressure",
            "reproduction_or_recurrence",
            "ecological_role",
            "relationship_to_civilization",
            "reason_for_persistence",
        )
        for field_name in creature_required:
            value = creature.get(field_name)
            if value is None or value == "" or value == []:
                _issue(
                    issues,
                    "ECOLOGY",
                    "missing_creature_system",
                    f"{path}.{field_name}",
                    f"creature lacks {field_name}",
                    "ecology contract",
                    "describe the dependency or explicit recurrence mechanism",
                )

    # Population is validated at zone/packet scale.  A room with no creature is intentionally
    # valid; this gate checks bounded habitats, aggregate caps, group references, and presence
    # layers instead of imposing the old one-creature-per-room wilderness rule.
    for finding in validate_population_records(packet.records, known_rooms):
        category = (
            "ECOLOGY"
            if finding.code
            in {
                "missing_habitat",
                "missing_energy_input",
                "missing_recurrence",
                "invalid_rarity",
                "legacy_bestiary_metaphysics",
                "over_capacity",
                "missing_population_subject",
            }
            else "POPULATION"
        )
        _issue(
            issues,
            category,
            finding.code,
            finding.path,
            finding.message,
            "AETHRYN_BESTIARY_AND_POPULATION_SYSTEM.md",
            finding.action,
            severity=finding.severity,
        )

    # Quest records are optional for legacy packets, but when present they must pass the same
    # reference/graph/canon gate before a package can be materialized.  Existing seed quest files
    # remain compatible because the quest validator normalizes their old `steps` shape.
    quest_report = validate_quest_records(packet.records, source=packet.packet_id)
    for finding in quest_report.findings:
        _issue(
            issues,
            "QUEST",
            finding.code,
            f"{finding.quest_id}:{finding.path}" if finding.path else finding.quest_id,
            finding.message,
            finding.source or "AETHRYN_QUEST_SYSTEM.md",
            finding.action,
            severity=finding.severity,
        )

    for index, flow in enumerate(packet.records.get("economy_flows", ())):
        path = f"records.economy_flows[{index}]"
        for field_name in (
            "source",
            "sink",
            "resource",
            "purpose",
            "transport",
            "inventory_provenance",
        ):
            if not flow.get(field_name):
                _issue(
                    issues,
                    "ECONOMY",
                    "incomplete_flow",
                    f"{path}.{field_name}",
                    f"economy flow lacks {field_name}",
                    "economy contract",
                    "identify the source, sink, use, transport, and inventory provenance",
                )

    for index, dungeon in enumerate(packet.records.get("dungeons", ())):
        path = f"records.dungeons[{index}]"
        for field_name in (
            "built_by",
            "original_purpose",
            "historical_layer",
            "failure",
            "current_occupants",
            "why_not_reclaimed",
            "entrance_logic",
            "gameplay_purpose",
            "revelation",
            "aftermath",
        ):
            if not dungeon.get(field_name):
                _issue(
                    issues,
                    "DUNGEON",
                    "incomplete_dungeon",
                    f"{path}.{field_name}",
                    f"dungeon lacks {field_name}",
                    "generation_contract.yaml",
                    "complete the dungeon record before compilation",
                )
        grammar = dungeon.get("traversal_grammar", [])
        if grammar != [
            "threshold",
            "orientation",
            "escalation",
            "revelation",
            "choice",
            "aftermath",
        ]:
            _issue(
                issues,
                "DUNGEON",
                "bad_grammar",
                f"{path}.traversal_grammar",
                "dungeon grammar is incomplete or out of order",
                "generation_contract.yaml",
                "use threshold, orientation, escalation, revelation, choice, aftermath",
            )

    for index, state in enumerate(packet.records.get("state_changes", ())):
        path = f"records.state_changes[{index}]"
        allowed = set(str(value) for value in state.get("reversible_values", ()))
        actions = state.get("actions")
        if actions is None:
            continue
        if not isinstance(actions, list):
            _issue(
                issues,
                "STATE",
                "invalid_actions",
                f"{path}.actions",
                "state actions must be a list of mappings",
                "state mutation contract",
                "declare actions as a list with command, target, from, and to fields",
            )
            continue
        for action_index, action in enumerate(actions):
            action_path = f"{path}.actions[{action_index}]"
            if not isinstance(action, dict):
                _issue(
                    issues,
                    "STATE",
                    "invalid_action",
                    action_path,
                    "state action must be a mapping",
                    "state mutation contract",
                    "declare one action mapping per validated transition",
                )
                continue
            for field_name in ("command", "target", "from", "to"):
                if not action.get(field_name):
                    _issue(
                        issues,
                        "STATE",
                        "incomplete_action",
                        f"{action_path}.{field_name}",
                        f"state action lacks {field_name}",
                        "state mutation contract",
                        "declare command, target, from, and to before publication",
                    )
            if action.get("from") not in allowed or action.get("to") not in allowed:
                _issue(
                    issues,
                    "STATE",
                    "action_value_outside_schema",
                    action_path,
                    "state action transition uses a value outside reversible_values",
                    "state mutation contract",
                    "add both transition values to reversible_values or correct the action",
                )
            if action.get("from") == action.get("to"):
                _issue(
                    issues,
                    "STATE",
                    "no_state_change",
                    action_path,
                    "state action source and destination are identical",
                    "state mutation contract",
                    "choose a different destination value for a reversible transition",
                )
            aliases = action.get("aliases")
            if aliases is not None and (
                not isinstance(aliases, list)
                or not all(isinstance(alias, str) and alias.strip() for alias in aliases)
            ):
                _issue(
                    issues,
                    "STATE",
                    "invalid_aliases",
                    f"{action_path}.aliases",
                    "state action aliases must be a list of non-empty strings",
                    "state mutation contract",
                    "declare aliases as a YAML list or omit the optional field",
                )
            if "required_item" in action and not isinstance(action.get("required_item"), str):
                _issue(
                    issues,
                    "STATE",
                    "invalid_required_item",
                    f"{action_path}.required_item",
                    "state action required_item must be text",
                    "state mutation contract",
                    "use a stable item prototype id or omit required_item",
                )
            if "consume_item" in action and not isinstance(action.get("consume_item"), bool):
                _issue(
                    issues,
                    "STATE",
                    "invalid_consume_item",
                    f"{action_path}.consume_item",
                    "state action consume_item must be true or false",
                    "state mutation contract",
                    "use a YAML boolean and declare required_item when consuming it",
                )
            if action.get("consume_item") and not action.get("required_item"):
                _issue(
                    issues,
                    "STATE",
                    "consume_without_item",
                    action_path,
                    "state action cannot consume an undeclared item",
                    "state mutation contract",
                    "add required_item or set consume_item to false",
                )

    # Structured material culture is an optional packet extension. Validate its source catalog
    # before compilation and retain packet-relative paths in every finding.
    for index, anchor in enumerate(packet.records.get("material_culture", ())):
        catalog_path = Path(str(anchor.get("catalog_path", "")))
        if not catalog_path.is_absolute():
            catalog_path = repo / catalog_path
        try:
            from kernel.world.material_culture import load_catalog, validate_catalog

            culture_report = validate_catalog(load_catalog(catalog_path))
            for issue in culture_report.issues:
                _issue(
                    issues,
                    issue.category,
                    issue.code,
                    f"records.material_culture[{index}].{issue.path}",
                    issue.message,
                    issue.authority,
                    issue.action,
                    severity=issue.severity,
                )
        except (OSError, ValueError) as exc:
            _issue(
                issues,
                "ITEM",
                "culture_catalog_load_failed",
                f"records.material_culture[{index}].catalog_path",
                f"could not load material-culture catalog {catalog_path}: {exc}",
                "material_culture.yaml",
                "correct catalog_path and ensure the catalog passes material-culture validation",
            )

    state_schemas = {
        str(state.get("key")): state
        for state in packet.records.get("state_changes", ())
        if state.get("key")
    }
    for index, pressure in enumerate(packet.records.get("quest_pressures", ())):
        gate = pressure.get("state_gate")
        if gate is None:
            continue
        path = f"records.quest_pressures[{index}].state_gate"
        if not isinstance(gate, dict):
            _issue(
                issues,
                "STATE",
                "invalid_state_gate",
                path,
                "state_gate must be a mapping with key and active_values",
                "state mutation contract",
                "declare state_gate as a mapping or remove the optional field",
            )
            continue
        gate_key = gate.get("key")
        active_values = gate.get("active_values")
        if not isinstance(gate_key, str) or not gate_key:
            _issue(
                issues,
                "STATE",
                "incomplete_state_gate",
                f"{path}.key",
                "state_gate lacks a stable state key",
                "state mutation contract",
                "reference a state_changes key declared by this packet",
            )
            continue
        if not isinstance(active_values, list) or not active_values:
            _issue(
                issues,
                "STATE",
                "invalid_gate_values",
                f"{path}.active_values",
                "state_gate active_values must be a non-empty list",
                "state mutation contract",
                "declare one or more allowed active state values",
            )
            continue
        gated_state = state_schemas.get(gate_key)
        if gated_state is None:
            _issue(
                issues,
                "STATE",
                "unknown_state_gate_key",
                f"{path}.key",
                f"state_gate references undeclared state {gate_key!r}",
                "state mutation contract",
                "reference a state_changes.key from this packet",
            )
            continue
        allowed = {str(value) for value in gated_state.get("reversible_values", ())}
        if any(str(value) not in allowed for value in active_values):
            _issue(
                issues,
                "STATE",
                "gate_value_outside_schema",
                f"{path}.active_values",
                "state_gate uses a value outside the gated state's reversible_values",
                "state mutation contract",
                "use only values declared by the referenced state record",
            )

    packet_records = {kind: tuple(rows) for kind, rows in packet.records.items()}
    presentations = build_packet_presentations(packet, packet_records)
    for prose_finding in validate_presentations(packet, presentations, packet_records):
        _issue(
            issues,
            "ROOM_PROSE",
            prose_finding.code,
            prose_finding.path,
            prose_finding.message,
            "AETHRYN_ROOM_PRESENTATION_SPEC.md",
            prose_finding.action,
        )
    for room_id, presentation in presentations.items():
        status = str(presentation.get("prose_status", "GENERATED_LOCAL"))
        if status in {"CANON_LOCKED", "CANON_WORKING"}:
            _issue(
                issues,
                "ROOM_PROSE",
                "generated_prose_promotion",
                f"records.rooms[{room_id}].prose_status",
                f"generated room prose is marked {status}",
                "AETHRYN_ROOM_PRESENTATION_SPEC.md",
                "keep generated prose GENERATED_LOCAL or provide an AUTHORED_LOCAL override",
            )
    similarity = similarity_report(presentations)
    if similarity["duplicate_groups"]:
        _issue(
            issues,
            "ROOM_PROSE",
            "duplicate_room_prose",
            "records.rooms",
            "generated room prose contains unchanged long-description groups",
            "AETHRYN_ROOM_PRESENTATION_SPEC.md",
            "write room-specific prose while retaining only necessary regional terminology",
        )

    for kind, rows in packet.records.items():
        expected = packet.required_content_counts.get(kind)
        if expected is not None and len(rows) != expected:
            _issue(
                issues,
                "PACKET",
                "count_mismatch",
                f"required_content_counts.{kind}",
                f"packet declares {expected} {kind} but contains {len(rows)}",
                "packet contract",
                "change the count or add the missing records",
            )
    searchable = " ".join(str(value).casefold() for value in packet.records.values())
    if any(term in searchable for term in OPEN_QUESTION_TERMS):
        _issue(
            issues,
            "CANON",
            "open_question_leakage",
            "records",
            "packet appears to answer an unresolved global question as objective prose",
            "canon.yaml",
            "rewrite it as rumor, disputed testimony, or contradictory evidence",
        )
    if "accidental divine strike" in searchable or "divine strike was accidental" in searchable:
        _issue(
            issues,
            "CANON",
            "strike_drift",
            "records",
            "packet describes the Divine Strike as accidental",
            "canon.yaml",
            "state that the strike was deliberate or keep local interpretation explicitly disputed",
        )
    if "netharion was born a god" in searchable or "natural-born god" in searchable:
        _issue(
            issues,
            "CANON",
            "netharion_drift",
            "records",
            "packet describes Netharion as natural-born",
            "canon.yaml",
            "describe Netharion as the first artificial god",
        )

    input_digest = content_digest(packet)
    verdict = cast(
        ValidationVerdict,
        "FAIL" if any(issue.severity == "error" for issue in issues) else "CLEAN",
    )
    return ValidationReport(verdict=verdict, issues=tuple(issues), input_digest=input_digest)


def validate_map_concordance(path: Path) -> list[ValidationIssue]:
    """Validate the design concordance against the locked region and topology registries."""
    issues: list[ValidationIssue] = []
    if not path.is_file():
        _issue(
            issues,
            "MAP",
            "missing_concordance",
            str(path),
            "map concordance does not exist",
            "Aethryn pipeline",
            "create design/map_concordance.yaml",
        )
        return issues
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("regions") if isinstance(raw, dict) else None
    expected = {row["id"] for row in canon.regions()}
    actual = set(rows) if isinstance(rows, dict) else set()
    for region_id in sorted(expected - actual):
        _issue(
            issues,
            "MAP",
            "missing_region",
            f"regions.{region_id}",
            f"canon region {region_id!r} has no map concordance row",
            "canon.yaml",
            "add the region without changing its locked name",
        )
    for region_id in sorted(actual - expected):
        _issue(
            issues,
            "MAP",
            "unknown_region",
            f"regions.{region_id}",
            f"map concordance contains non-canon region {region_id!r}",
            "canon.yaml",
            "remove it or obtain an approved canon change",
        )
    if raw.get("topology_source") != "content/seeds/aethryn/world_graph.yaml":
        _issue(
            issues,
            "MAP",
            "wrong_topology_authority",
            "topology_source",
            "map concordance does not name world_graph.yaml as topology authority",
            "world_graph.yaml",
            "set the canonical topology source explicitly",
        )
    if not raw.get("prohibitions"):
        _issue(
            issues,
            "MAP",
            "missing_prohibitions",
            "prohibitions",
            "map concordance does not record decorative-route prohibitions",
            "world pipeline rules",
            "state that poster routes are orientation only",
        )
    try:
        worldgraph.load_graph()
    except SeedError as exc:
        _issue(
            issues,
            "GEOGRAPHY",
            "topology_invalid",
            "world_graph.yaml",
            str(exc),
            "world_graph.yaml",
            "repair the machine-readable topology before compiling",
        )
    return issues


def format_report(report: ValidationReport) -> str:
    lines = [f"verdict: {report.verdict}", f"input_digest: {report.input_digest}"]
    if report.output_digest:
        lines.append(f"output_digest: {report.output_digest}")
    if not report.issues:
        lines.append("validation: CLEAN")
        return "\n".join(lines)
    lines.append(f"issues: {len(report.issues)}")
    for issue in report.issues:
        lines.extend(
            [
                f"- [{issue.severity}] {issue.category}/{issue.code} at {issue.path}",
                f"  {issue.message}",
                f"  authority: {issue.authority}",
                f"  action: {issue.action}",
            ]
        )
    return "\n".join(lines)
