#!/usr/bin/env python3
"""Census the Aethryn world and the CodeForge engine: a reproducible count of what actually exists.

The AAA-benchmark scorecard (docs/aaa_benchmark_scorecard.md) compares CodeForge/Aethryn against
industry targets. Its "Current Status" column must be MEASURED, not hand-typed and left to drift,
or it violates the ship's law (no claim without correspondence). This is that measurement: it loads
the flagship seed and reads a handful of engine constants, then prints a structured census. Re-run
it whenever the world grows and paste the fresh numbers into the scorecard's current column.

Content counts come from the seed YAML (the world is data). Generated-world scale is derived from
the wildlands trail-length budget, since booting the full ~26k-room world just to count rooms is
wasteful when the generator's own inputs already state the target. Engine constants (Orders, codes,
equipment slots) are read from their modules so a change there shows up here.

Run from the repo root:  python tools/census.py
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from kernel.world.seed import BLUEPRINTS_ROOT

SEED = BLUEPRINTS_ROOT / "aethryn"


def _load(name: str) -> dict:
    """Load one aethryn seed file as a dict of entities (empty if absent)."""
    path = SEED / name
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _count(name: str) -> int:
    return len(_load(name))


def _count_dir(subdir: str) -> int:
    """Count the seed files in a seed sub-directory (e.g. the authored quests in quests/)."""
    d = SEED / subdir
    return len(list(d.glob("*.yaml"))) if d.is_dir() else 0


def world_scale() -> dict[str, object]:
    """Authored rooms, plus the generated-room budget from the seed's procedural wilderness: every
    wildlands region's trail_length (a trail-chain) AND every field zone's width x height (an open
    field, kernel/world/fieldzone.py). Both are the generator's scale input at the default boot."""
    authored = _count("rooms.yaml")
    wild = _load("wildlands.yaml")
    fields = _load("fields.yaml")
    trail_rooms = sum(v.get("trail_length", 0) for v in wild.values() if isinstance(v, dict))
    field_rooms = sum(
        int(v.get("width", 0)) * int(v.get("height", 0))
        for v in fields.values()
        if isinstance(v, dict)
    )
    generated = trail_rooms + field_rooms
    return {
        "authored_rooms": authored,
        "wildlands_regions": len(wild),
        "field_regions": len(fields),
        "generated_regions": len(wild) + len(fields),
        "generated_rooms_base": generated,
        "total_rooms_default_scale": authored + generated,
    }


def items() -> dict[str, object]:
    data = _load("items.yaml")
    by_slot: Counter[str] = Counter()
    consumables = 0
    for entity in data.values():
        if not isinstance(entity, dict):
            continue
        if "slot" in entity:
            by_slot[entity["slot"]] += 1
        if "consume" in entity:
            consumables += 1
    equipment = sum(by_slot.values())
    return {
        "total_items": len(data),
        "equipment": equipment,
        "equipment_by_slot": dict(by_slot),
        "consumables": consumables,
        "materials_and_other": len(data) - equipment - consumables,
    }


def population() -> dict[str, object]:
    data = _load("npcs.yaml")
    tiers: Counter[str] = Counter()
    aggressive = afflicting = 0
    for entity in data.values():
        if not isinstance(entity, dict):
            continue
        tiers[entity.get("tier", "ambient")] += 1
        aggressive += 1 if entity.get("aggressive") else 0
        afflicting += 1 if ("inflicts" in entity or "special" in entity) else 0
    return {
        "authored_npcs": len(data),
        "bosses": tiers.get("boss", 0),
        "ambient_and_named": tiers.get("ambient", 0),
        "aggressive": aggressive,
        "afflicting": afflicting,
    }


def abilities() -> dict[str, object]:
    data = _load("abilities.yaml")
    kinds = Counter(v.get("kind", "?") for v in data.values() if isinstance(v, dict))
    return {"total_abilities": len(data), "by_kind": dict(kinds)}


def systems() -> dict[str, object]:
    """Engine constants read from their modules, so a change at the source shows here."""
    from kernel.world.equipment import SLOTS  # noqa: PLC0415
    from kernel.world.orders import ORDERS  # noqa: PLC0415
    from kernel.world.score_sheet_model import RESIST_ORDER  # noqa: PLC0415

    return {
        "orders_factions": len(ORDERS),
        "order_labels": list(ORDERS),
        "damage_resist_types": len(RESIST_ORDER),
        "equipment_slots": len(SLOTS),
    }


def engine() -> dict[str, object]:
    """Cheap engine metrics measured from the tree (LOC, module counts). Test count is measured
    separately via `pytest --collect-only`, recorded in the scorecard with its command."""
    root = Path(__file__).resolve().parent.parent
    # The section-2 restructure retired parts/ into kernel/ (engine + world + shelf) + adapters/
    # (the drivers). Measure the engine over both, so the count reflects the current layout.
    kernel = root / "kernel"
    adapters = root / "adapters"
    py = list(kernel.rglob("*.py")) + list(adapters.rglob("*.py")) + [root / "forge.py"]
    loc = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in py if p.is_file())
    return {
        "engine_modules": len(list(kernel.glob("*.py"))) + len(list(adapters.glob("*.py"))),
        "world_modules": len(list((kernel / "world").glob("*.py"))),
        "shelf_parts": len(list((kernel / "shelf").glob("*.py"))),
        "engine_python_loc": loc,
    }


def main() -> None:
    seed_counts: dict[str, object] = {
        "jobs_classes": _count("jobs.yaml"),
        "professions": _count("professions.yaml"),
        "recipes": _count("recipes.yaml"),
        "equipment_sets": _count("sets.yaml"),
        "zones": _count("zones.yaml"),
        "settlements": _count("settlements.yaml"),
        "dungeons": _count("dungeons.yaml"),
        "waystones_fast_travel": _count("waystones.yaml"),
        "authored_quests": _count_dir("quests"),
    }
    report: dict[str, dict[str, object]] = {
        "world_scale": world_scale(),
        "population": population(),
        "items": items(),
        "abilities": abilities(),
        "seed_counts": seed_counts,
        "systems": systems(),
        "engine": engine(),
    }
    print("Aethryn / CodeForge census (measured from the seed + engine)\n")
    for section, body in report.items():
        print(f"[{section}]")
        for key, value in body.items():
            print(f"  {key}: {value}")
        print()


if __name__ == "__main__":
    main()
