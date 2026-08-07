#!/usr/bin/env python3
"""Materialize Aethryn's generated world into a pure authored seed package.

The normal runtime is useful while the world is being designed: compact lore/topology manifests
feed deterministic factories. This command is the authoring pass. It boots that design once,
serializes the resulting rooms, NPCs, items, zones, gear, and quest workflows into a standalone
seed directory, and records the source contract in ``authoring_manifest.yaml``.

The resulting package contains no active fields, wildlands, cave, spiral, or underground manifests.
When selected with ``FORGE_AUTHORING_SNAPSHOT=/path/to/package``, the world loader treats the
package as authored data and does not invoke those generators at boot. The open graph remains intact
because
all exits, thresholds, settlement interiors, dungeon chambers, secrets, and lore-bearing
descriptions are materialized as ordinary seed records.

Examples::

    PYTHONPATH=. .venv/bin/python tools/materialize_aethryn.py --scale 1 \
        --output content/seeds/aethryn-authored-scale-1
    FORGE_SEED=aethryn FORGE_AUTHORING_SNAPSHOT=content/seeds/aethryn-authored-scale-1 \
        PYTHONPATH=. .venv/bin/python tools/census.py

Scale is deliberately an offline authoring cost. A million-room package is expected to be generated
on a content build host and deployed as a versioned seed artifact, not created during player boot.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

_GENERATED_MANIFESTS = {
    "fields.yaml",
    "wildlands.yaml",
    "underground.yaml",
    "spiral.yaml",
    "authored_zones.yaml",
}
_ROOT_DATA_OUTPUTS = {
    "rooms.yaml",
    "npcs.yaml",
    "items.yaml",
    "zones.yaml",
    "sets.yaml",
    "dungeons.yaml",
    "settlements.yaml",
    "quest.yaml",
    "population.yaml",
}
_POPULATION_RECORD_KINDS = {
    "creatures",
    "creature_specs",
    "population_profiles",
    "spawn_pools",
    "roaming_routes",
    "migration_rules",
    "encounter_groups",
    "crowd_specs",
    "ambient_presence",
    "population_states",
    "population_manifests",
}
_QUEST_RECORD_KINDS = {
    "quests",
    "quest_specs",
    "quest_arcs",
    "contract_templates",
    "public_events",
    "quest_pressures",
    "quest_world_effects",
    "quest_generation_profiles",
}


def _plain(value: Any) -> Any:
    """Convert seed TypedDicts and runtime containers into YAML-safe ordinary values."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_plain(item) for item in value]
        return sorted(values) if isinstance(value, (set, frozenset)) else values
    return value


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(_plain(data), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _npc_record(npc: dict[str, Any]) -> dict[str, Any]:
    record = dict(npc)
    # Runtime state is reinitialized by the seed loader; ambient is an assembly hint that pure mode
    # no longer needs because its quest board is materialized too.
    record.pop("next_line", None)
    record.pop("hp_now", None)
    record.pop("ambient", None)
    return record


def _item_record(item: dict[str, Any]) -> dict[str, Any]:
    record = dict(item)
    location = str(record.get("location", ""))
    record["location"] = location.removeprefix("room:")
    record.pop("prototype", None)
    record.pop("rarity", None)
    record.pop("durability", None)
    return record


def _zone_record(zone: dict[str, Any]) -> dict[str, Any]:
    return dict(zone)


def _population_records(source: Path) -> dict[str, list[dict[str, Any]]]:
    """Collect compiled population sidecars into the pure authored Seed artifact."""
    merged: dict[str, list[dict[str, Any]]] = {}
    for records_path in sorted((source / "generated").glob("*/records.yaml")):
        raw = yaml.safe_load(records_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            continue
        for kind in _POPULATION_RECORD_KINDS:
            rows = raw.get(kind, [])
            if isinstance(rows, list):
                merged.setdefault(kind, []).extend(_plain(rows))
    return merged


def _quest_records(source: Path) -> dict[str, list[dict[str, Any]]]:
    """Collect structured quest sidecars without replacing the legacy quest loader output."""
    merged: dict[str, list[dict[str, Any]]] = {}
    for records_path in sorted((source / "generated").glob("*/records.yaml")):
        raw = yaml.safe_load(records_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            continue
        for kind in _QUEST_RECORD_KINDS:
            rows = raw.get(kind, [])
            if isinstance(rows, list):
                merged.setdefault(kind, []).extend(_plain(rows))
    return merged


def _quest_filename(quest_id: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", quest_id.casefold()).strip("_")
    return f"materialized_{safe or 'quest'}.yaml"


def _copy_source_pack(source: Path, output: Path) -> None:
    """Copy the non-generated game systems so the snapshot remains a complete seed."""
    for path in source.iterdir():
        if path.name in _GENERATED_MANIFESTS or path.name in _ROOT_DATA_OUTPUTS:
            continue
        if path.name in {"authored", "quests"}:
            continue
        destination = output / path.name
        if path.is_file():
            shutil.copy2(path, destination)
        elif path.is_dir():
            shutil.copytree(path, destination)


def materialize(
    source: Path, output: Path, scale: int, *, overwrite: bool = False
) -> dict[str, int]:
    if output.exists():
        if not overwrite:
            raise SystemExit(f"output already exists: {output} (pass --overwrite to replace it)")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    os.environ["FORGE_SEED"] = "aethryn"
    os.environ["CODEFORGE_WILD_SCALE"] = str(scale)
    os.environ.pop("FORGE_AUTHORING_SNAPSHOT", None)

    # Import only after the scale and seed are pinned; world.py is the design-time assembly pass.
    from kernel.world import gearsets, quest, world, zones
    from kernel.world.authoring_prose import author_world
    from kernel.world.room_batches import apply_room_batches

    _copy_source_pack(source, output)
    author_world(world.WORLD, world.NPCS)
    # Hand-authored room batches are applied last so a delivered prose record wins over the
    # regional fallback voice while still sharing the same topology/link gates.
    batch_report = apply_room_batches(world.WORLD, world.NPCS, world.ITEMS)
    _write(output / "rooms.yaml", world.WORLD)
    _write(output / "npcs.yaml", {label: _npc_record(npc) for label, npc in world.NPCS.items()})
    _write(
        output / "items.yaml", {label: _item_record(item) for label, item in world.ITEMS.items()}
    )
    population = _population_records(source)
    if population:
        _write(output / "population.yaml", population)
    _write(output / "sets.yaml", gearsets.SETS)

    base_labels = {str(row["label"]) for row in world._story_zones}
    base_zones = {
        label: _zone_record(zone) for label, zone in zones.ZONES.items() if label in base_labels
    }
    extra_zones = {
        label: _zone_record(zone) for label, zone in zones.ZONES.items() if label not in base_labels
    }
    _write(output / "zones.yaml", base_zones)
    _write(output / "authored_zones.yaml", extra_zones)

    dungeons = {
        str(row["room"]): {key: value for key, value in row.items() if key != "room"}
        for row in (world._dungeons or [])
    }
    settlements = {
        str(row["room"]): {key: value for key, value in row.items() if key != "room"}
        for row in (world._settlements or [])
    }
    _write(output / "dungeons.yaml", dungeons)
    _write(output / "settlements.yaml", settlements)

    specs = quest.all_specs()
    if specs:
        _write(output / "quest.yaml", specs[0])
        for spec in specs[1:]:
            _write(output / "quests" / _quest_filename(spec["id"]), spec)
    quest_records = _quest_records(source)
    materialized_quests = {str(spec["id"]) for spec in specs}
    for row in quest_records.get("quests", []) + quest_records.get("quest_specs", []):
        quest_id = str(row.get("id", ""))
        if quest_id and quest_id not in materialized_quests:
            _write(output / "quests" / _quest_filename(quest_id), row)
            materialized_quests.add(quest_id)
    if quest_records:
        _write(output / "quest_records.yaml", quest_records)

    counts = {
        "rooms": len(world.WORLD),
        "npcs": len(world.NPCS),
        "items": len(world.ITEMS),
        "base_zones": len(base_zones),
        "authored_zones": len(extra_zones),
        "dungeons": len(dungeons),
        "settlements": len(settlements),
        "quests": len(specs),
        "structured_quests": len(materialized_quests),
        "room_batches": batch_report["batches"],
        "batched_room_descriptions": batch_report["rooms"],
        "population_records": sum(len(rows) for rows in population.values()),
    }
    _write(
        output / "authoring_manifest.yaml",
        {
            "mode": "pure_authoring",
            "seed": "aethryn",
            "scale": scale,
            "source_contract": "content/seeds/aethryn/generation_contract.yaml",
            "topography": "content/seeds/aethryn/world_graph.yaml",
            "lore": "docs/aethryn_lore_bible.md",
            "canon": "content/seeds/aethryn/canon.yaml",
            "prose": "kernel/world/authoring_prose.py",
            "prose_status": "authored_regional_landmark_and_enemy_pass",
            "room_batch_status": "validated_and_baked",
            "counts": counts,
            "runtime_generators": "disabled; this package is the authored output",
        },
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, default=1, help="offline authoring scale (>= 1)")
    parser.add_argument(
        "--output",
        type=Path,
        help="snapshot directory (default: content/seeds/aethryn-authored-scale-<scale>)",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.scale < 1:
        parser.error("--scale must be >= 1")
    root = Path(__file__).resolve().parent.parent
    source = root / "content" / "seeds" / "aethryn"
    output = args.output or root / "content" / "seeds" / f"aethryn-authored-scale-{args.scale}"
    counts = materialize(source, output, args.scale, overwrite=args.overwrite)
    print(f"materialized pure Aethryn authoring package: {output}")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
