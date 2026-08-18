#!/usr/bin/env python3
"""CARD: world_audit -- a read-only census of the assembled Aethryn world graph.

Phase-One build manifest, generated not hand-written: loads the full playable world (the aethryn
seed PLUS the procedural Forgeward Road) exactly as the engine does, walks the exit graph from the
spawn, and emits machine-readable stats -- room count, reachability, orphans, unresolved exits,
dead-ends, and the wider-compass usage (compound directions + noun exits). Reproducible from any
commit; the honest answer to "does the world exist," measured, never asserted.

Usage:  python scripts/world_audit.py [--json PATH]   (default: docs/world/phase1_manifest.json)
"""

from __future__ import annotations

import json
import os
import sys
from collections import deque
from pathlib import Path

# Load the aethryn seed as the flagship world (the engine's default may differ per env).
os.environ.setdefault("FORGE_SEED", "aethryn")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kernel.world.world import DIRECTIONS, START_ROOM, WORLD  # noqa: E402
from kernel.world.zones import ZONES  # noqa: E402

CARDINAL = {"north", "south", "east", "west", "up", "down"}
COMPOUND = {"northeast", "northwest", "southeast", "southwest"}


def _zone_coverage(rooms: dict) -> dict:
    """Layer-2 geography coverage: which rooms belong to an area, which Reaches are represented,
    and which of the Level 1-300 bands the metadata zones cover (with any gaps named honestly)."""
    zoned: set[str] = set()
    regions: dict[str, int] = {}
    covered = [False] * 301  # index by level; 1..300 meaningful
    for zone in ZONES.values():
        zoned.update(zone["rooms"])
        region = zone.get("region")
        if region:
            regions[region] = regions.get(region, 0) + len(zone["rooms"])
        lo, hi = zone.get("level_min"), zone.get("level_max")
        if lo is not None and hi is not None:
            for lvl in range(lo, hi + 1):
                covered[lvl] = True
    unzoned = sorted(set(rooms) - zoned)
    gaps: list[str] = []
    lvl = 1
    while lvl <= 300:  # noqa: PLR2004
        if not covered[lvl]:
            start = lvl
            while lvl <= 300 and not covered[lvl]:  # noqa: PLR2004
                lvl += 1
            gaps.append(f"{start}-{lvl - 1}")
        else:
            lvl += 1
    return {
        "zones_total": len(ZONES),
        "zones_with_metadata": sum(1 for z in ZONES.values() if z.get("region")),
        "regions": dict(sorted(regions.items())),
        "rooms_in_a_zone": len(zoned),
        "rooms_without_zone": len(unzoned),
        "unzoned_rooms": unzoned,
        "level_band_gaps": gaps,
    }


def audit() -> dict:
    rooms = WORLD
    total = len(rooms)

    # Reachability: BFS from the spawn over every exit destination.
    seen: set[str] = set()
    q: deque[str] = deque([START_ROOM])
    seen.add(START_ROOM)
    while q:
        here = rooms[q.popleft()]
        for dest in here["exits"].values():
            if dest in rooms and dest not in seen:
                seen.add(dest)
                q.append(dest)

    orphans = sorted(set(rooms) - seen)
    unresolved: list[str] = []
    total_exits = 0
    compound_exits = 0
    noun_exits = 0
    dead_ends: list[str] = []
    for label, room in rooms.items():
        exits = room["exits"]
        if len(exits) <= 1:
            dead_ends.append(label)
        for direction, dest in exits.items():
            total_exits += 1
            if dest not in rooms:
                unresolved.append(f"{label} -{direction}-> {dest}")
            if direction in COMPOUND:
                compound_exits += 1
            elif direction not in CARDINAL and direction not in DIRECTIONS:
                noun_exits += 1  # a threshold keyed by a place-noun

    return {
        "spawn": START_ROOM,
        "rooms_total": total,
        "rooms_reachable_from_spawn": len(seen),
        "orphans": orphans,
        "orphan_count": len(orphans),
        "exits_total": total_exits,
        "unresolved_exits": unresolved,
        "unresolved_exit_count": len(unresolved),
        "compound_direction_exits": compound_exits,
        "noun_exits": noun_exits,
        "dead_end_rooms": len(dead_ends),
        "fully_connected": len(orphans) == 0 and len(unresolved) == 0,
        "geography": _zone_coverage(rooms),
    }


def main() -> int:
    out = Path("docs/world/phase1_manifest.json")
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
    report = audit()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    for key in (
        "rooms_total",
        "rooms_reachable_from_spawn",
        "orphan_count",
        "exits_total",
        "unresolved_exit_count",
        "compound_direction_exits",
        "noun_exits",
        "fully_connected",
    ):
        print(f"{key}: {report[key]}")
    geo = report["geography"]
    print(f"zones_total: {geo['zones_total']} (with metadata: {geo['zones_with_metadata']})")
    print(f"regions: {', '.join(geo['regions'])}")
    print(
        f"rooms_in_a_zone: {geo['rooms_in_a_zone']}  "
        f"rooms_without_zone: {geo['rooms_without_zone']}"
    )
    print(f"level_band_gaps (1-300): {geo['level_band_gaps'] or 'none'}")
    print(f"manifest written: {out}")
    return 0 if report["fully_connected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
