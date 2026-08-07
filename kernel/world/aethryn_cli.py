# ruff: noqa: E501

"""CARD: aethryn_cli -- builder commands for inspectable Aethryn packet production."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from kernel.world import canon
from kernel.world.aethryn_compiler import (
    CompilationError,
    compile_packet,
    diff_artifacts,
    explain_packet,
    provenance_for,
    publish_package,
)
from kernel.world.aethryn_corpus import audit_world_corpus, format_corpus_audit
from kernel.world.aethryn_delivery import (
    create_hotfix,
    format_semantic_diff,
    inspect_cache,
    semantic_diff,
)
from kernel.world.aethryn_population import encounter_group, simulate_population
from kernel.world.aethryn_quests import (
    QuestValidationFinding,
    deterministic_contract_preview,
    format_validation_report,
    simulate_public_event,
    simulate_quest,
    validate_quest_records,
)
from kernel.world.aethryn_validation import (
    format_report,
    load_packet,
    validate_map_concordance,
    validate_packet,
)
from kernel.world.material_culture import (
    format_catalog_report,
    load_catalog,
    validate_catalog,
    weapon_budget,
)

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PACKET = (
    _ROOT
    / "content"
    / "seeds"
    / "aethryn"
    / "design"
    / "packets"
    / "veridia_greenhold_living_slice.yaml"
)
_PACKET_ROOT = _ROOT / "content" / "seeds" / "aethryn" / "design" / "packets"


def _packet_path(argument: str | None) -> Path:
    if argument:
        candidate = Path(argument)
        if candidate.is_file():
            return candidate
        candidate = _PACKET_ROOT / argument
        if candidate.is_file():
            return candidate
    return _DEFAULT_PACKET


def _clean(label: str) -> tuple[int, str]:
    return 0, f"{label}: CLEAN"


def _filtered_packet_report(path: Path, category: str) -> tuple[int, str]:
    packet = load_packet(path)
    report = validate_packet(packet, root=_ROOT)
    issues = tuple(issue for issue in report.issues if issue.category == category)
    filtered = report.__class__(
        verdict="FAIL" if issues else "CLEAN", issues=issues, input_digest=report.input_digest
    )
    return (1 if issues else 0), format_report(filtered)


def run(argv: list[str]) -> tuple[int, str]:
    if not argv:
        return 2, _usage()
    command, rest = argv[0], argv[1:]
    try:
        if command == "explain":
            return 0, explain_packet(_packet_path(rest[0] if rest else None), root=_ROOT)
        if command == "validate-packet":
            if not rest:
                return 2, "usage: world validate-packet <path>"
            packet = load_packet(_packet_path(rest[0]))
            report = validate_packet(packet, root=_ROOT)
            return (1 if report.verdict == "FAIL" else 0), format_report(report)
        if command == "compile-packet":
            if not rest:
                return 2, "usage: world compile-packet <path> [--output DIR] [--cache DIR]"
            path, output, cache = _parse_output(rest)
            staging, manifest = compile_packet(
                _packet_path(path), output_dir=output, root=_ROOT, cache_dir=cache
            )
            return 0, f"compiled: {staging}\noutput_digest: {manifest.output_digest}"
        if command == "materialize":
            packet_argument, output, publish = _parse_materialize(rest)
            staging, manifest = compile_packet(
                _packet_path(packet_argument), output_dir=output, root=_ROOT
            )
            lines = [f"staged: {staging}", f"output_digest: {manifest.output_digest}"]
            if publish:
                target, rollback = publish_package(staging)
                lines.append(f"published: {target}")
                lines.append(f"rollback: {rollback or '(no previous artifact)'}")
            else:
                lines.append(
                    "publication: not requested; pass --stage-only only when staging is intended"
                )
            return 0, "\n".join(lines)
        if command == "diff":
            if len(rest) != 2:
                return 2, "usage: world diff <artifact-a> <artifact-b>"
            if Path(rest[0]).is_dir() and Path(rest[1]).is_dir():
                return 0, format_semantic_diff(semantic_diff(Path(rest[0]), Path(rest[1])))
            return 0, diff_artifacts(Path(rest[0]), Path(rest[1]))
        if command == "hotfix":
            if len(rest) != 4 or rest[2] != "--output":
                return 2, "usage: world hotfix <base-package> <candidate-package> --output DIR"
            diff = create_hotfix(Path(rest[0]), Path(rest[1]), Path(rest[3]))
            return 0, format_semantic_diff(diff) + f"\nhotfix: {Path(rest[3]) / 'hotfix.yaml'}"
        if command == "cache-inspect":
            cache = Path(rest[0]) if rest else _ROOT / ".aethryn_cache"
            return 0, yaml.safe_dump(list(inspect_cache(cache)), sort_keys=False).rstrip()
        if command == "provenance":
            if not rest:
                return 2, "usage: world provenance <id> [--package DIR]"
            package = (
                Path(rest[2])
                if len(rest) >= 3 and rest[1] == "--package"
                else _ROOT
                / "content"
                / "seeds"
                / "aethryn"
                / "generated"
                / "veridia_greenhold_living_slice"
            )
            return 0, provenance_for(package, rest[0])
        if command == "find-orphans":
            packet = load_packet(_packet_path(rest[0] if rest else None))
            report = validate_packet(packet, root=_ROOT)
            issues = tuple(issue for issue in report.issues if issue.code == "orphan_room")
            filtered = report.__class__(
                verdict="FAIL" if issues else "CLEAN",
                issues=issues,
                input_digest=report.input_digest,
            )
            return (1 if issues else 0), format_report(filtered)
        if command == "economy-check":
            code, packet_text = _filtered_packet_report(
                _packet_path(rest[0] if rest else None), "ECONOMY"
            )
            catalog_text = format_catalog_report(validate_catalog(load_catalog()))
            return max(code, 1 if "FAIL" in catalog_text else 0), packet_text + "\n" + catalog_text
        if command in {
            "item-check",
            "weapon-check",
            "armor-check",
            "crafting-check",
            "merchant-check",
            "loot-check",
        }:
            return _catalog_check(command)
        if command == "inspect-item":
            return _inspect_catalog_record(rest, "prototypes")
        if command == "inspect-material":
            return _inspect_catalog_record(rest, "materials")
        if command == "inspect-recipe":
            return _inspect_catalog_record(rest, "recipes")
        if command == "inspect-merchant-stock":
            return _inspect_catalog_record(rest, "merchant_stock")
        if command in {
            "item-lineage",
            "item-provenance",
            "recipe-tree",
            "merchant-preview",
            "loot-preview",
            "simulate-crafting",
            "simulate-stock",
        }:
            return _catalog_query(command, rest)
        if command in {
            "find-unobtainable-items",
            "find-unproducible-items",
            "find-orphaned-recipes",
            "find-broken-sets",
            "find-balance-outliers",
            "find-economic-loops",
            "find-duplicate-uniques",
        }:
            return _catalog_find(command)
        if command == "ecology-check":
            return _filtered_packet_report(_packet_path(rest[0] if rest else None), "ECOLOGY")
        if command in {"world bestiary-check", "bestiary-check"}:
            return _filtered_packet_report(_packet_path(rest[0] if rest else None), "ECOLOGY")
        if command == "population-check":
            packet = load_packet(_packet_path(rest[0] if rest else None))
            report = validate_packet(packet, root=_ROOT)
            issues = tuple(
                issue for issue in report.issues if issue.category in {"POPULATION", "ECOLOGY"}
            )
            filtered = report.__class__(
                verdict="FAIL" if issues else "CLEAN",
                issues=issues,
                input_digest=report.input_digest,
            )
            return (1 if issues else 0), format_report(filtered)
        if command == "inspect-creature":
            return _inspect_record(
                _packet_path(rest[1] if len(rest) > 1 else None),
                rest[0] if rest else "",
                {"creatures", "creature_specs"},
            )
        if command == "inspect-population":
            return _inspect_record(
                _packet_path(rest[1] if len(rest) > 1 else None),
                rest[0] if rest else "",
                {
                    "population_profiles",
                    "crowd_specs",
                    "spawn_pools",
                    "roaming_routes",
                    "migration_rules",
                },
            )
        if command == "population-map":
            return _population_map(
                _packet_path(rest[1] if len(rest) > 1 else None), rest[0] if rest else ""
            )
        if command == "encounter-preview":
            return _encounter_preview(
                _packet_path(rest[1] if len(rest) > 1 else None), rest[0] if rest else ""
            )
        if command == "simulate-population":
            return _simulate_population(rest)
        if command in {
            "find-overpopulated",
            "find-empty-zones",
            "find-habitat-conflicts",
            "find-orphaned-creatures",
        }:
            return _population_find(command, _packet_path(rest[0] if rest else None))
        if command in {
            "quest-check",
            "quest-reference-check",
            "quest-graph-check",
            "quest-reward-check",
            "quest-consequence-check",
            "find-broken-quests",
            "find-unreachable-quest-states",
            "find-unobtainable-objectives",
            "find-missing-quest-references",
            "find-duplicate-rewards",
            "find-quest-economic-loops",
            "find-canon-leaking-quests",
            "find-quests-without-consequences",
            "find-overused-quest-targets",
        }:
            return _quest_check(command, _packet_path(rest[0] if rest else None))
        if command == "inspect-quest":
            return _inspect_record(
                _packet_path(rest[1] if len(rest) > 1 else None),
                rest[0] if rest else "",
                {"quests", "quest_specs"},
            )
        if command == "inspect-pressure":
            return _inspect_record(
                _packet_path(rest[1] if len(rest) > 1 else None),
                rest[0] if rest else "",
                {"quest_pressures"},
            )
        if command == "inspect-arc":
            return _inspect_record(
                _packet_path(rest[1] if len(rest) > 1 else None),
                rest[0] if rest else "",
                {"quest_arcs"},
            )
        if command in {"quest-graph", "quest-lineage", "quest-provenance"}:
            return _quest_query(command, rest)
        if command == "simulate-quest":
            return _simulate_quest(rest)
        if command == "simulate-public-event":
            return _simulate_public_event(rest)
        if command == "preview-contract":
            return _preview_contract(rest)
        if command == "canon-check":
            return _verdict("canon-check", canon.check_canon())
        if command == "map-concordance-check":
            return _verdict(
                "map-concordance-check",
                [
                    f"{issue.path}: {issue.message}; action: {issue.action}"
                    for issue in validate_map_concordance(
                        _ROOT / "content" / "seeds" / "aethryn" / "design" / "map_concordance.yaml"
                    )
                ],
            )
        if command == "full-world-check":
            audit = audit_world_corpus(_ROOT)
            return (1 if audit.verdict == "FAIL" else 0), format_corpus_audit(audit)
    except (CompilationError, OSError, ValueError) as exc:
        return 1, f"refused: {exc}"
    return 2, f"unknown Aethryn builder subcommand: {command!r}\n\n{_usage()}"


def _parse_output(args: list[str]) -> tuple[str, Path | None, Path | None]:
    if not args:
        raise ValueError("usage: world compile-packet <path> [--output DIR] [--cache DIR]")
    path = args[0]
    output = None
    cache = None
    index = 1
    while index < len(args):
        if index + 1 >= len(args) or args[index] not in {"--output", "--cache"}:
            raise ValueError("usage: world compile-packet <path> [--output DIR] [--cache DIR]")
        destination = Path(args[index + 1])
        if args[index] == "--output":
            output = destination
        else:
            cache = destination
        index += 2
    return path, output, cache


def _parse_materialize(args: list[str]) -> tuple[str | None, Path | None, bool]:
    path: str | None = None
    output: Path | None = None
    publish = True
    index = 0
    while index < len(args):
        value = args[index]
        if value == "--publish":
            publish = True
        elif value == "--stage-only":
            publish = False
        elif value == "--output" and index + 1 < len(args):
            index += 1
            output = Path(args[index])
        elif value.startswith("--"):
            raise ValueError("usage: world materialize [packet] [--output DIR] [--stage-only]")
        elif path is None:
            path = value
        else:
            raise ValueError("usage: world materialize [packet] [--output DIR] [--stage-only]")
        index += 1
    return path, output, publish


def _verdict(label: str, problems: list[str]) -> tuple[int, str]:
    if not problems:
        return _clean(label)
    return 1, f"{label}: {len(problems)} problem(s)\n" + "\n".join(
        f"- {problem}" for problem in problems
    )


def _packet_records(path: Path) -> dict[str, list[dict[str, Any]]]:
    packet = load_packet(path)
    return {kind: [dict(row) for row in rows] for kind, rows in packet.records.items()}


def _inspect_record(path: Path, stable_id: str, kinds: set[str]) -> tuple[int, str]:
    records = _packet_records(path)
    for kind in kinds:
        for row in records.get(kind, []):
            if str(row.get("id")) == stable_id:
                return 0, yaml.safe_dump({"kind": kind, "record": row}, sort_keys=False).rstrip()
    return 1, f"not found: {stable_id}"


def _population_map(path: Path, zone: str) -> tuple[int, str]:
    records = _packet_records(path)
    lines = [f"population-map: {zone}"]
    for row in records.get("population_profiles", []):
        if str(row.get("zone", row.get("parent_zone", zone))) == zone:
            rooms = ", ".join(
                str(room) for room in row.get("candidate_rooms", row.get("rooms", []))
            )
            lines.append(f"- {row.get('id')}: {rooms or '(no rooms)'}")
    for row in records.get("crowd_specs", []):
        lines.append(f"- crowd {row.get('id')}: {', '.join(row.get('rooms', []))}")
    return 0, "\n".join(lines)


def _encounter_preview(path: Path, group_id: str) -> tuple[int, str]:
    for row in _packet_records(path).get("encounter_groups", []):
        if str(row.get("id")) == group_id:
            group = encounter_group(row)
            lines = [
                f"encounter: {group.stable_id}",
                f"formation: {group.formation}",
                f"size: {group.minimum_size}-{group.maximum_size}",
            ]
            lines.append(
                "composition: "
                + ", ".join(
                    f"{key} {bounds[0]}-{bounds[1]}" for key, bounds in group.composition.items()
                )
            )
            lines.append(
                "cohesion: "
                f"{group.cohesion}; aggression: {group.shared_aggression}; "
                f"pursuit: {group.pursuit_distance}"
            )
            return 0, "\n".join(lines)
    return 1, f"not found: {group_id}"


def _simulate_population(args: list[str]) -> tuple[int, str]:
    if not args:
        return 2, "usage: world simulate-population <zone> --ticks <n> --seed <seed> [packet]"
    zone = args[0]
    ticks, seed = 1, 0
    packet_arg: str | None = None
    index = 1
    while index < len(args):
        if args[index] == "--ticks" and index + 1 < len(args):
            ticks = int(args[index + 1])
            index += 2
            continue
        if args[index] == "--seed" and index + 1 < len(args):
            seed = int(args[index + 1])
            index += 2
            continue
        packet_arg = args[index]
        index += 1
    manifest = simulate_population(_packet_records(_packet_path(packet_arg)), zone, ticks, seed)
    payload = {
        "zone": manifest.zone,
        "tick": manifest.tick,
        "digest": manifest.digest,
        "states": [state.__dict__ for state in manifest.states],
    }
    return 0, yaml.safe_dump(payload, sort_keys=False).rstrip()


def _population_find(command: str, path: Path) -> tuple[int, str]:
    records = _packet_records(path)
    problems: list[str] = []
    if command == "find-overpopulated":
        for row in records.get("population_profiles", []):
            if row.get("carrying_capacity") and int(row.get("population_max", 0)) > int(
                row["carrying_capacity"]
            ):
                problems.append(str(row.get("id")))
    elif command == "find-empty-zones":
        if not records.get("population_profiles") and not records.get("crowd_specs"):
            problems.append("packet has no population or crowd records")
    elif command == "find-orphaned-creatures":
        subjects = {str(row.get("creature_id")) for row in records.get("population_profiles", [])}
        subjects |= {
            str(key)
            for row in records.get("encounter_groups", [])
            for key in (row.get("composition", {}) or {})
        }
        problems.extend(
            str(row.get("id"))
            for row in records.get("creatures", [])
            if str(row.get("id")) not in subjects
        )
    else:
        report = validate_packet(load_packet(path), root=_ROOT)
        problems.extend(
            issue.message
            for issue in report.issues
            if issue.code
            in {
                "missing_habitat",
                "unknown_population_room",
                "roaming_allow_forbid_conflict",
                "over_capacity",
            }
        )
    return _verdict(command, problems)


def _quest_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    records = _packet_records(path)
    return {
        kind: rows
        for kind, rows in records.items()
        if kind.startswith("quest") or kind in {"quests", "contract_templates", "public_events"}
    }


def _quest_check(command: str, path: Path) -> tuple[int, str]:
    records = _packet_records(path)
    report = validate_quest_records(records, source=str(path))
    selected = report.findings
    if command in {
        "quest-reference-check",
        "find-missing-quest-references",
        "find-unobtainable-objectives",
    }:
        selected = tuple(
            f
            for f in selected
            if f.code in {"missing_reference", "missing_objective", "missing_objective_type"}
        )
    elif command in {"quest-graph-check", "find-unreachable-quest-states", "find-broken-quests"}:
        selected = tuple(
            f
            for f in selected
            if f.code
            in {
                "missing_start_state",
                "missing_terminal_state",
                "invalid_transition",
                "missing_event_type",
                "unreachable_state",
                "dead_state",
                "invalid_cycle",
            }
        )
    elif command in {"quest-reward-check", "find-duplicate-rewards", "find-quest-economic-loops"}:
        selected = tuple(
            f for f in selected if f.code in {"invalid_reward", "unique_reward_on_repeatable"}
        )
    elif command in {"quest-consequence-check", "find-quests-without-consequences"}:
        quest_rows = records.get("quests", records.get("quest_specs", []))
        selected = tuple(
            f
            for f in selected
            if f.code in {"missing_provenance"}
            or any(
                str(row.get("id")) == f.quest_id
                and not row.get("consequences", row.get("world_effects", []))
                for row in quest_rows
            )
        )
        for row in quest_rows:
            if not row.get("consequences", row.get("world_effects", [])):
                selected += (
                    QuestValidationFinding(
                        "missing_consequence",
                        str(row.get("id")),
                        "quest has no declared world consequence",
                        "consequences",
                        str(path),
                        "add a visible scoped effect or mark this as a trivial contract",
                ),
            )
    elif command == "find-canon-leaking-quests":
        selected = tuple(f for f in selected if f.code == "canon_leak")
    elif command == "find-overused-quest-targets":
        targets: dict[str, int] = defaultdict(int)
        for row in records.get("quests", records.get("quest_specs", [])):
            for target in row.get("target_ids", []) or []:
                targets[str(target)] += 1
        selected = tuple(
            QuestValidationFinding(
                "overused_target",
                target,
                f"target appears in {count} quest records",
                "target_ids",
                str(path),
                "spread local pressure across compatible targets",
            )
            for target, count in sorted(targets.items())
            if count > 3
        )
    filtered = report.__class__(tuple(selected))
    return (1 if filtered.verdict == "FAIL" else 0), format_validation_report(filtered)


def _quest_query(command: str, args: list[str]) -> tuple[int, str]:
    if not args:
        return 2, f"usage: world {command} <id> [packet]"
    quest_id = args[0]
    record = next(
        (
            row
            for row in _packet_records(_packet_path(args[1] if len(args) > 1 else None)).get(
                "quests", []
            )
            if str(row.get("id")) == quest_id
        ),
        None,
    )
    if record is None:
        return 1, f"not found: {quest_id}"
    if command == "quest-graph":
        return 0, yaml.safe_dump(
            {
                "id": quest_id,
                "start": record.get("start_state", record.get("start")),
                "transitions": record.get("transitions", record.get("steps", [])),
                "terminal": record.get("terminal_states", record.get("terminal", [])),
            },
            sort_keys=False,
        ).rstrip()
    if command == "quest-lineage":
        return 0, yaml.safe_dump(
            {
                "id": quest_id,
                "pressure": record.get("pressure_id", ""),
                "arc_membership": [
                    row.get("id")
                    for row in _packet_records(
                        _packet_path(args[1] if len(args) > 1 else None)
                    ).get("quest_arcs", [])
                    if quest_id in row.get("quest_ids", [])
                ],
                "sources": record.get("source_design_ids", []),
            },
            sort_keys=False,
        ).rstrip()
    return 0, yaml.safe_dump(
        {
            "id": quest_id,
            "provenance": record.get("provenance", {}),
            "source_design_ids": record.get("source_design_ids", []),
            "generation_seed": record.get("generation_seed"),
            "generator_version": record.get("generator_version"),
        },
        sort_keys=False,
    ).rstrip()


def _simulate_quest(args: list[str]) -> tuple[int, str]:
    if not args:
        return 2, "usage: world simulate-quest <id> [packet]"
    path = _packet_path(args[1] if len(args) > 1 else None)
    row = next(
        (
            candidate
            for candidate in _packet_records(path).get("quests", [])
            if str(candidate.get("id")) == args[0]
        ),
        None,
    )
    if row is None:
        return 1, f"not found: {args[0]}"
    return 0, yaml.safe_dump(simulate_quest(row), sort_keys=False).rstrip()


def _simulate_public_event(args: list[str]) -> tuple[int, str]:
    if not args:
        return 2, "usage: world simulate-public-event <id> [packet]"
    path = _packet_path(args[1] if len(args) > 1 else None)
    row = next(
        (
            candidate
            for candidate in _packet_records(path).get("public_events", [])
            if str(candidate.get("id")) == args[0]
        ),
        None,
    )
    if row is None:
        return 1, f"not found: {args[0]}"
    state = simulate_public_event(row, {"preview": int(row.get("success_threshold", 1))})
    return 0, yaml.safe_dump(state.__dict__, sort_keys=False).rstrip()


def _preview_contract(args: list[str]) -> tuple[int, str]:
    if not args:
        return 2, "usage: world preview-contract <template-id> --seed <seed> [packet]"
    template_id, seed, packet_arg = args[0], 0, None
    index = 1
    while index < len(args):
        if args[index] == "--seed" and index + 1 < len(args):
            seed = int(args[index + 1])
            index += 2
        else:
            packet_arg = args[index]
            index += 1
    row = next(
        (
            candidate
            for candidate in _packet_records(_packet_path(packet_arg)).get("contract_templates", [])
            if str(candidate.get("id")) == template_id
        ),
        None,
    )
    if row is None:
        return 1, f"not found: {template_id}"
    return 0, yaml.safe_dump(deterministic_contract_preview(row, seed), sort_keys=False).rstrip()


def _catalog_check(command: str) -> tuple[int, str]:
    report = validate_catalog(load_catalog())
    if command == "item-check":
        categories = {"ITEM", "MATERIAL", "PROVENANCE", "CANON", "PLACEMENT"}
    elif command == "weapon-check":
        categories = {"BALANCE"}
    elif command == "armor-check":
        categories = {"EQUIPMENT", "BALANCE"}
    elif command == "crafting-check":
        categories = {"CRAFTING", "PROFESSION"}
    elif command == "merchant-check":
        categories = {"ECONOMY"}
    else:
        categories = {"LOOT"}
    issues = tuple(issue for issue in report.issues if issue.category in categories)
    filtered = report.__class__(
        verdict="FAIL" if issues else "CLEAN", issues=issues, input_digest=report.input_digest
    )
    return (1 if issues else 0), format_catalog_report(filtered)


def _catalog_record(stable_id: str, section: str) -> dict[str, Any] | None:
    catalog = load_catalog()
    row = getattr(catalog, section, {}).get(stable_id)
    return dict(row) if row is not None else None


def _inspect_catalog_record(args: list[str], section: str) -> tuple[int, str]:
    if not args:
        return 2, f"usage: world inspect-{section.replace('_', '-')} <id>"
    row = _catalog_record(args[0], section)
    if row is None:
        return 1, f"not found: {args[0]}"
    return 0, yaml.safe_dump(
        {"kind": section, "id": args[0], "record": row}, sort_keys=False
    ).rstrip()


def _catalog_query(command: str, args: list[str]) -> tuple[int, str]:
    if not args:
        return 2, f"usage: world {command} <id>"
    catalog = load_catalog()
    stable_id = args[0]
    if command == "merchant-preview":
        section, key = "merchant_stock", "merchant stock"
    elif command == "loot-preview":
        section, key = "loot_profiles", "loot profile"
    elif command == "simulate-stock":
        section, key = "merchant_stock", "merchant stock"
    elif command in {"simulate-crafting", "recipe-tree"}:
        section, key = "recipes", "recipe"
    else:
        section, key = "prototypes", "item"
    row = getattr(catalog, section, {}).get(stable_id)
    if row is None:
        return 1, f"not found: {stable_id}"
    if command == "item-provenance":
        return 0, yaml.safe_dump(
            {
                "id": stable_id,
                "provenance": {"catalog": str(catalog.metadata), "record": dict(row)},
            },
            sort_keys=False,
        ).rstrip()
    if command == "item-lineage":
        recipes = {
            rid: r
            for rid, r in catalog.recipes.items()
            if str(r.get("output_prototype")) == stable_id
            or any(
                str(req.get("prototype_id")) == stable_id
                for req in r.get("requirements", [])
                if isinstance(req, dict)
            )
        }
        return 0, yaml.safe_dump(
            {"item": stable_id, "recipes": recipes, "materials": row.get("materials", [])},
            sort_keys=False,
        ).rstrip()
    if command == "recipe-tree":
        return 0, _recipe_tree(catalog, stable_id)
    if command == "simulate-crafting":
        requirements = row.get("requirements", [])
        return 0, yaml.safe_dump(
            {
                "recipe": stable_id,
                "profession": row.get("profession", ""),
                "station": row.get("station", ""),
                "inputs": requirements,
                "output": row.get("output_prototype", ""),
                "reachable": all(
                    str(req.get("prototype_id")) in catalog.prototypes
                    for req in requirements
                    if isinstance(req, dict)
                ),
            },
            sort_keys=False,
        ).rstrip()
    if command == "merchant-preview":
        return 0, yaml.safe_dump(
            {
                "profile": stable_id,
                "stock": row.get("ordinary_stock", {}),
                "conditional_stock": row.get("conditional_stock", {}),
                "sources": row.get("supply_sources", {}),
                "imports": row.get("imported_goods", {}),
                "markup": row.get("markup", 1.0),
            },
            sort_keys=False,
        ).rstrip()
    if command == "loot-preview":
        return 0, yaml.safe_dump(
            {
                "profile": stable_id,
                "source": row.get("source_id", ""),
                "body_class": row.get("body_class", ""),
                "guaranteed": row.get("guaranteed", []),
                "weighted": row.get("weighted", {}),
                "reason": row.get("production_reason", ""),
            },
            sort_keys=False,
        ).rstrip()
    if command == "simulate-stock":
        ticks, seed = 1, 0
        index = 1
        while index < len(args):
            if args[index] == "--ticks" and index + 1 < len(args):
                ticks = int(args[index + 1])
                index += 2
                continue
            if args[index] == "--seed" and index + 1 < len(args):
                seed = int(args[index + 1])
                index += 2
                continue
            index += 1
        stock = {}
        for item_id, bounds in row.get("ordinary_stock", {}).items():
            lo, hi = int(bounds[0]), int(bounds[1])
            digest = int(
                __import__("hashlib")
                .sha256(f"{stable_id}:{item_id}:{seed}".encode())
                .hexdigest()[:8],
                16,
            )
            stock[item_id] = sum(
                lo + ((digest + tick) % (hi - lo + 1)) for tick in range(max(0, ticks))
            )
        return 0, yaml.safe_dump(
            {"profile": stable_id, "ticks": ticks, "seed": seed, "stock_units": stock},
            sort_keys=False,
        ).rstrip()
    return 0, yaml.safe_dump(
        {"kind": key, "id": stable_id, "record": dict(row)}, sort_keys=False
    ).rstrip()


def _recipe_tree(catalog: Any, recipe_id: str, seen: set[str] | None = None) -> str:
    seen = set() if seen is None else seen
    if recipe_id in seen:
        return f"{recipe_id}: cycle"
    seen.add(recipe_id)
    row = catalog.recipes[recipe_id]
    lines = [
        f"{recipe_id} -> {row.get('output_prototype')} ({row.get('profession', '')} at {row.get('station', '')})"
    ]
    for req in row.get("requirements", []):
        input_id = str(req.get("prototype_id"))
        parents = [
            rid
            for rid, candidate in catalog.recipes.items()
            if str(candidate.get("output_prototype")) == input_id
        ]
        lines.append(
            f"  {req.get('quantity')}x {input_id}"
            + (f" <- {parents[0]}" if parents else " (source)")
        )
    return "\n".join(lines)


def _catalog_find(command: str) -> tuple[int, str]:
    catalog = load_catalog()
    problems: list[str] = []
    if command in {"find-unobtainable-items", "find-unproducible-items"}:
        produced = {str(row.get("output_prototype")) for row in catalog.recipes.values()}
        stocked = {
            item
            for row in catalog.merchant_stock.values()
            for item in row.get("ordinary_stock", {})
        }
        looted = {
            item
            for row in catalog.loot_profiles.values()
            for item in row.get("weighted", {})
            if item != "nothing"
        }
        sourced = set(catalog.materials)
        reachable = (
            produced
            | stocked
            | looted
            | sourced
            | {item for row in catalog.placements.values() for item in row.get("items", [])}
        )
        problems.extend(
            item_id
            for item_id in catalog.prototypes
            if item_id not in reachable and not catalog.prototypes[item_id].get("unique")
        )
    elif command == "find-orphaned-recipes":
        for recipe_id, row in catalog.recipes.items():
            if str(row.get("output_prototype")) not in catalog.prototypes or any(
                str(req.get("prototype_id")) not in catalog.prototypes
                for req in row.get("requirements", [])
                if isinstance(req, dict)
            ):
                problems.append(recipe_id)
    elif command == "find-broken-sets":
        for set_id, row in catalog.equipment_sets.items():
            if any(piece not in catalog.prototypes for piece in row.get("pieces", [])):
                problems.append(set_id)
    elif command == "find-balance-outliers":
        for item_id, row in catalog.prototypes.items():
            if row.get("category") == "weapon" and weapon_budget(row) > 12:
                problems.append(item_id)
    elif command == "find-economic-loops":
        # A catalog stock source must not be the same item output at a price below its declared
        # input value; the detailed economy simulator remains an explicit future extension.
        for profile_id, row in catalog.merchant_stock.items():
            if row.get("markup", 1.0) < 1.0:
                problems.append(profile_id)
    elif command == "find-duplicate-uniques":
        unique_ids = [item_id for item_id, row in catalog.prototypes.items() if row.get("unique")]
        for item_id in unique_ids:
            if any(
                item_id in row.get("ordinary_stock", {}) for row in catalog.merchant_stock.values()
            ):
                problems.append(item_id)
    return _verdict(command, problems)


def _usage() -> str:
    return "\n".join(
        [
            "Aethryn World Builder:",
            "  world explain <packet>",
            "  world validate-packet <path>",
            "  world compile-packet <path> [--output DIR] [--cache DIR]",
            "  world materialize [packet] [--output DIR] [--stage-only]",
            "  world diff <artifact-a> <artifact-b>",
            "  world hotfix <base-package> <candidate-package> --output DIR",
            "  world cache-inspect [DIR]",
            "  world provenance <id> [--package DIR]",
            "  world find-orphans [packet]",
            "  world economy-check [packet]",
            "  world item-check | weapon-check | armor-check | crafting-check | merchant-check | loot-check",
            "  world inspect-item <id> | inspect-material <id> | inspect-recipe <id>",
            "  world inspect-merchant-stock <id>",
            "  world item-lineage <id> | item-provenance <id> | recipe-tree <id>",
            "  world merchant-preview <profile-id> | loot-preview <profile-id>",
            "  world simulate-crafting <recipe-id> | simulate-stock <profile-id> --ticks <n> --seed <seed>",
            "  world find-unobtainable-items | find-unproducible-items | find-orphaned-recipes",
            "  world find-broken-sets | find-balance-outliers | find-economic-loops | find-duplicate-uniques",
            "  world ecology-check [packet]",
            "  world bestiary-check [packet]",
            "  world population-check [packet]",
            "  world inspect-creature <id> [packet]",
            "  world inspect-population <id> [packet]",
            "  world population-map <zone> [packet]",
            "  world encounter-preview <group-id> [packet]",
            "  world simulate-population <zone> --ticks <n> --seed <seed> [packet]",
            "  world find-overpopulated [packet]",
            "  world find-empty-zones [packet]",
            "  world find-habitat-conflicts [packet]",
            "  world find-orphaned-creatures [packet]",
            "  world quest-check | quest-reference-check | quest-graph-check [packet]",
            "  world quest-reward-check | quest-consequence-check [packet]",
            "  world inspect-quest <id> | inspect-pressure <id> | inspect-arc <id> [packet]",
            "  world quest-graph <id> | quest-lineage <id> | quest-provenance <id> [packet]",
            "  world simulate-quest <id> | simulate-public-event <id> [packet]",
            "  world preview-contract <template-id> --seed <seed> [packet]",
            "  world find-broken-quests | find-unreachable-quest-states | find-unobtainable-objectives",
            "  world find-missing-quest-references | find-duplicate-rewards | find-quest-economic-loops",
            "  world find-canon-leaking-quests | find-quests-without-consequences | find-overused-quest-targets",
            "  world canon-check",
            "  world map-concordance-check",
            "  world full-world-check",
        ]
    )
