"""CARD: worldgraph -- the region topology: canonical land + sea adjacency, and reachability.

The prompt's second pillar is a world represented as an expandable graph. This is that graph at the
region scale: it loads the canonical adjacency (seeds/aethryn/world_graph.yaml), validates it
against canon (every region present, every neighbour a real region, every sea a real sea), and
computes which regions are reachable from the spawn. That reachability is what turns `world
find-unreachable` from an honest stub into a real check, and lets `world validate` prove no region
is stranded.

Two rules shape the model, both from the source seed:
  - Land links are UNDIRECTED for reachability even though they are authored directed (The Deepreach
    lists the surface it runs beneath, but the surface does not list it back). So the validator
    checks referential integrity, never symmetry.
  - Two regions that border the same sea are reachable from each other by sea route. That is the
    only thing connecting the island and sky regions, which have no land neighbours.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.world import canon
from kernel.world.seed import SeedError, _UniqueKeyLoader

_GRAPH_PATH = canon.AETHRYN_DIR / "world_graph.yaml"

# The spawn region: reachability is measured from here (the world's front door, Veridia 1-30).
DEFAULT_START = "veridia"


def load_graph(path: Path | None = None) -> dict[str, Any]:
    """Read and VALIDATE the region topology. Fails loud (SeedError) if a region is missing, names a
    neighbour or sea that canon does not know, or links to itself, so a broken graph never loads."""
    where = path if path is not None else _GRAPH_PATH
    if not where.exists():
        raise SeedError(f"World graph file not found: {where}")
    data = yaml.load(where.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise SeedError(f"World graph file is not a mapping: {where}")

    seas = set(data.get("seas", []))
    if not seas:
        raise SeedError("world graph: 'seas' must list the world's bodies of water")

    region_rows = data.get("regions")
    if not isinstance(region_rows, dict):
        raise SeedError("world graph: 'regions' must be a mapping of region id -> {land, seas}")

    known_regions = {r["id"] for r in canon.regions()}
    missing = known_regions - set(region_rows)
    if missing:
        raise SeedError(f"world graph: no topology row for canon region(s) {sorted(missing)}")

    for region_id, row in region_rows.items():
        if region_id not in known_regions:
            raise SeedError(f"world graph {region_id!r}: not a canon region")
        for neighbour in row.get("land", []):
            if neighbour == region_id:
                raise SeedError(f"world graph {region_id!r}: a region cannot border itself")
            if neighbour not in known_regions:
                raise SeedError(f"world graph {region_id!r}: unknown land neighbour {neighbour!r}")
        for sea in row.get("seas", []):
            if sea not in seas:
                raise SeedError(f"world graph {region_id!r}: unknown sea {sea!r}")
    return data


def _rows(graph: dict[str, Any] | None) -> dict[str, Any]:
    return (graph or load_graph())["regions"]


def neighbors(region_id: str, graph: dict[str, Any] | None = None) -> set[str]:
    """Every region reachable in one hop from region_id: land links (treated as undirected, so a
    one-way listing still connects) plus any region that borders a shared sea."""
    rows = _rows(graph)
    if region_id not in rows:
        raise SeedError(f"unknown region {region_id!r}")
    found: set[str] = set()
    # Land, both directions: what this region lists, and what lists this region.
    found.update(rows[region_id].get("land", []))
    for other, row in rows.items():
        if region_id in row.get("land", []):
            found.add(other)
    # Sea: anyone sharing a sea with this region.
    my_seas = set(rows[region_id].get("seas", []))
    if my_seas:
        for other, row in rows.items():
            if other != region_id and my_seas & set(row.get("seas", [])):
                found.add(other)
    found.discard(region_id)
    return found


def reachable_from(start: str = DEFAULT_START, graph: dict[str, Any] | None = None) -> set[str]:
    """Every region reachable from start by land or sea (breadth-first over undirected edges)."""
    graph = graph or load_graph()
    if start not in _rows(graph):
        raise SeedError(f"unknown start region {start!r}")
    seen = {start}
    frontier = [start]
    while frontier:
        for nxt in neighbors(frontier.pop(), graph):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return seen


def unreachable_regions(
    start: str = DEFAULT_START, graph: dict[str, Any] | None = None
) -> list[str]:
    """The `find-unreachable` check: canon regions that cannot be reached from the spawn by any land
    or sea route. Empty means the whole world is connected."""
    graph = graph or load_graph()
    return sorted(set(_rows(graph)) - reachable_from(start, graph))


def region_detail(region_id: str, graph: dict[str, Any] | None = None) -> str:
    """The `inspect` view of one region: its canon facts (name, status, threat band) and its place
    in the graph (land neighbours, sea neighbours, whether the spawn can reach it)."""
    graph = graph or load_graph()
    if region_id not in _rows(graph):
        raise SeedError(f"unknown region {region_id!r}")
    region = next((r for r in canon.regions() if r["id"] == region_id), None)
    if region is None:
        raise SeedError(f"region {region_id!r} is in the graph but not in canon")
    row = _rows(graph)[region_id]
    land = sorted(row.get("land", []))
    sea_kin = sorted(neighbors(region_id, graph) - set(land))
    reached = region_id in reachable_from(DEFAULT_START, graph)
    return "\n".join(
        [
            f"{region['name']}  [{region_id}]",
            f"  canon_status {region['canon_status']} | "
            f"threat {region['threat_min']}-{region['threat_max']}",
            f"  land neighbours: {', '.join(land) if land else '(none)'}",
            f"  reachable by sea: {', '.join(sea_kin) if sea_kin else '(none)'}",
            f"  seas: {', '.join(row.get('seas', [])) or '(landlocked)'}",
            f"  reachable from {DEFAULT_START}: {'yes' if reached else 'NO'}",
        ]
    )


def graph_lines(graph: dict[str, Any] | None = None) -> str:
    """The `graph` view: every region and its land neighbours + seas, in canon order."""
    graph = graph or load_graph()
    rows = _rows(graph)
    lines = ["Region topology (land -> [neighbours] | seas):"]
    for region in canon.regions():
        row = rows[region["id"]]
        land = ", ".join(row.get("land", [])) or "-"
        seas = ", ".join(row.get("seas", [])) or "landlocked"
        lines.append(f"  {region['id']:<18} land: {land:<45} seas: {seas}")
    return "\n".join(lines)
