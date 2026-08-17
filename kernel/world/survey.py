"""CARD: survey -- the Surveyor: a read-only developer audit of the Aethryn world map.

The prompt's developer tools ask for a `world` command family that VALIDATES the world without
touching it: duplicate ids, broken references (a location placed in a region that does not exist),
canon drift, and unreachable regions. This is that read-only half. The Surveyor never edits the
world; it inspects the shipped seed and reports, and its verdict is the truth of the map. The
region topology it reasons over lives in kernel/world/worldgraph.py; the mutating half
(generate-area, promote, export, import) lives in kernel/world/area_store.py.

Every check is a pure function over the seed data returning a list of human-readable violation
lines (empty == clean), so each is unit-testable in isolation and `validate` is just their union.
`run` is the thin dispatcher the CLI (tools/world.py) and the Make button call.
"""

from __future__ import annotations

from typing import Any

import yaml

from kernel.shelf import table
from kernel.world import canon, worldgraph
from kernel.world.seed import BlueprintError, _UniqueKeyLoader

# The seed files the Surveyor reads. Regions come from canon; these carry the placed locations.
_LOCATION_FILES = ("settlements.yaml", "dungeons.yaml")
_ZONE_FILE = "waystones.yaml"

# The read-only subcommands. The mutating half (generate-area, promote, export, ...) lives in
# area_store; only `import` and `reset-dev-state` are still planned.
_COMMANDS = (
    "validate",
    "check-canon",
    "list-regions",
    "list-locations",
    "find-broken-references",
    "find-unreachable",
    "inspect",
    "graph",
)


def _records(filename: str) -> dict[str, dict[str, Any]]:
    """Every top-level record in an aethryn seed file, keyed by id (skipping a template block)."""
    data = yaml.load(
        (canon.AETHRYN_DIR / filename).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader  # noqa: S506
    )
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k != "template" and isinstance(v, dict)}


def locations() -> list[dict[str, Any]]:
    """Every placed location (settlements + dungeons), each tagged with its id and source file, so
    the Surveyor can report where a defect lives."""
    found: list[dict[str, Any]] = []
    for filename in _LOCATION_FILES:
        for loc_id, record in _records(filename).items():
            found.append({"id": loc_id, "source": filename, **record})
    return found


def duplicate_ids() -> list[str]:
    """Any id that appears in more than one world file (the _UniqueKeyLoader catches WITHIN a file;
    this catches a collision ACROSS files, which would make `world inspect <id>` ambiguous)."""
    seen: dict[str, str] = {}
    violations: list[str] = []
    for filename in (_ZONE_FILE, *_LOCATION_FILES):
        for rec_id in _records(filename):
            if rec_id in seen:
                violations.append(
                    f"duplicate id '{rec_id}' in {filename} (already in {seen[rec_id]})"
                )
            else:
                seen[rec_id] = filename
    return violations


def broken_references() -> list[str]:
    """A placed location must sit in a region that canon actually knows. Catches a typo or a stale
    region name that would strand a settlement or dungeon off the map."""
    known_regions = canon.locked_region_names()
    violations: list[str] = []
    for loc in locations():
        zone = loc.get("zone")
        if zone not in known_regions:
            violations.append(
                f"location '{loc['id']}' ({loc['source']}) references unknown region {zone!r}"
            )
    return violations


def faction_references() -> list[str]:
    """Any location that names a `faction` canon does not know (the seed's 'invalid faction
    references' check). Satisfied today (no location carries one yet), but live the moment content
    references a faction, so a typo cannot slip a settlement under a nonexistent power."""
    known = canon.world_faction_ids()
    violations: list[str] = []
    for loc in locations():
        faction = loc.get("faction")
        if faction is not None and faction not in known:
            violations.append(
                f"location '{loc['id']}' ({loc['source']}) references unknown faction {faction!r}"
            )
    return violations


def unreachable() -> list[str]:
    """Any canon region the spawn cannot reach by land or sea (a stranded region is a broken map).
    Delegates to the topology graph; a graph that names an unknown region raises from load_graph."""
    return [
        f"region '{r}' is unreachable from {worldgraph.DEFAULT_START}"
        for r in worldgraph.unreachable_regions()
    ]


def validate() -> list[str]:
    """The aggregate `world validate`: duplicate ids, broken references, canon drift, unreachable
    regions, and invalid faction references. Empty means the world map is consistent, faithful,
    fully connected, and every faction reference resolves."""
    return (
        duplicate_ids()
        + broken_references()
        + faction_references()
        + canon.check_canon()
        + unreachable()
    )


def _format_regions() -> str:
    rows = [[r["id"], r["name"], f"{r['threat_min']}-{r['threat_max']}"] for r in canon.regions()]
    if not rows:
        return "Regions (canon-locked): none"
    grid = table.render(rows, headers=["id", "name", "threat"], border=False)
    return "Regions (canon-locked):\n" + grid


def _format_locations() -> str:
    locs = sorted(locations(), key=lambda loc: (loc["zone"], loc.get("level", 0), loc["id"]))
    rows = [
        [
            loc["id"],
            loc["name"],
            loc["zone"],
            f"L{loc.get('level', '?')}",
            loc["source"].removesuffix(".yaml"),
        ]
        for loc in locs
    ]
    header = f"Locations ({len(locs)} placed):"
    if not rows:
        return header + " none"
    grid = table.render(rows, headers=["id", "name", "zone", "level", "kind"], border=False)
    return header + "\n" + grid


def _verdict(label: str, violations: list[str]) -> tuple[int, str]:
    """Turn a violation list into an exit code + a clean report (0 clean, 1 problems found)."""
    if not violations:
        return 0, f"{label}: CLEAN"
    body = "\n".join(f"  - {v}" for v in violations)
    return 1, f"{label}: {len(violations)} problem(s)\n{body}"


def run(argv: list[str]) -> tuple[int, str]:  # noqa: PLR0911
    """Dispatch a `world` read-only subcommand to its check. Returns (exit_code, text). An unknown
    or not-yet-built subcommand is refused honestly (never faked) with the usage listing."""
    if not argv:
        return 2, _usage()
    command = argv[0]
    if command == "check-canon":
        return _verdict("check-canon", canon.check_canon())
    if command == "find-broken-references":
        return _verdict("find-broken-references", broken_references())
    if command == "validate":
        return _verdict("world validate", validate())
    if command == "find-unreachable":
        return _verdict("find-unreachable", unreachable())
    if command == "list-regions":
        return 0, _format_regions()
    if command == "list-locations":
        return 0, _format_locations()
    if command == "graph":
        return 0, worldgraph.graph_lines()
    if command == "inspect":
        if len(argv) < 2:  # noqa: PLR2004
            return 2, "usage: world inspect <region-id>"
        try:
            return 0, worldgraph.region_detail(argv[1])
        except BlueprintError as exc:  # unknown region id
            return 1, f"refused: {exc}"
    return 2, f"unknown or not-yet-built subcommand: {command!r}\n\n{_usage()}"


def _usage() -> str:
    available = "\n".join(f"  world {c}" for c in _COMMANDS)
    return (
        "The Surveyor: read-only Aethryn world validation.\n\n"
        f"Available now:\n{available}\n\n"
        "Area generation (mutating): world generate-area / preview-area / promote / export /\n"
        "list-areas (see kernel/world/area_store.py). Planned: world import / reset-dev-state."
    )
