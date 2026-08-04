"""CARD: worldgen -- the TWO-LAYER region generator of the World Topology Doctrine (Phase 3).

A region is built in two layers, then judged by every gate:

  1. MISSION / structure layer: a spec places the LANDMARKS (towns, dungeons, a peak) and the
     DELIBERATE bottlenecks (a river's declared ford/bridge crossings). Structure first, so the
     story anchors and the one-bridge-over-the-river are intentional, not accidents.
  2. SPATIAL fill layer: a deterministic HEIGHTMAP (seeded) gives every cell an elevation; a RIVER
     follows the heightmap DOWNHILL (elevation, not decoration); terrain is read from height (peaks
     -> hill, lowland -> forest, the river channel -> impassable water save at its crossings); and
     the walkable exits are DERIVED by the field backing (kernel/field.py) from terrain adjacency +
     passability. The trail a player walks is one path THROUGH the field, never the field itself.

  * `generate_region(spec)` -> a Region carrying the rooms, the topology verdict, and whether every
    landmark is reachable (progression). It NEVER hides a bad shape: `spec.corridor=True` forces a
    1-wide chain and the region honestly comes back TRAIL_SHAPED (the sabotage the gate must catch).
  * `populate_region(region, life)` -> the LIFE layer: scatter ambient foes, gather nodes, and a
    handful of guardians across the open field, so a field PLAYS like the living wilderness the
    trail-chains gave (foes to fell, nodes to harvest, a lord to hunt), never a bare map. It reuses
    the same bestiary/gather parts kernel/world/wildlands.py fills the trails with, so the same
    cull/forage boards keep routing after a zone flips from a trail to a field.

Deterministic: the same seed yields the same region (a seeded RNG, no wall-clock). Fails loud on a
degenerate size or a landmark placed on impassable terrain. Status: PROTOTYPED (Phase 3).
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

from kernel.world.bestiary import make_beast, make_notable
from kernel.world.field import Cell, Stack, build_field
from kernel.world.seed import Npc
from kernel.world.topology import WORLD_SHAPED, TopologyReport, audit_topology
from kernel.world.wildlands import gatherable_materials

_ORTHO = [(0, 1), (0, -1), (1, 0), (-1, 0)]


class WorldgenError(ValueError):
    """A region that cannot be generated (degenerate size, or a landmark on a wall). Fails loud."""


@dataclass(frozen=True)
class Landmark:
    """A mission-layer anchor placed on the map: a town, a dungeon, a peak. `kind='peak'` also
    raises a summit (a vertical Stack) so the region has real elevation, not just labels."""

    at: tuple[int, int]
    name: str
    kind: str = "site"


@dataclass(frozen=True)
class RegionSpec:
    """The mission-layer order for a region: its size, a seed, its landmarks, and (optionally) a
    river traced from `river_source` with DECLARED `crossings` (x, y, 'ford'|'bridge')."""

    name: str
    width: int
    height: int
    seed: int = 0
    landmarks: tuple[Landmark, ...] = ()
    river_source: tuple[int, int] | None = None
    crossings: tuple[tuple[int, int, str], ...] = ()
    roads: bool = True  # thread a road between the landmarks -- a trail THROUGH the open field
    corridor: bool = False  # SABOTAGE: force a 1-wide linear chain so the gate can be tested


@dataclass(frozen=True)
class Region:
    """A generated region and every gate's verdict on it."""

    name: str
    rooms: dict[str, dict]
    start: str
    topology: TopologyReport
    landmarks_reachable: bool  # progression: can the player reach every anchor?
    river: tuple[tuple[int, int], ...] = ()

    @property
    def world_shaped(self) -> bool:
        return self.topology.verdict == WORLD_SHAPED

    @property
    def ok(self) -> bool:
        return self.world_shaped and self.landmarks_reachable


@dataclass(frozen=True)
class LifeSpec:
    """The order for BREATHING LIFE into a region's open field: which biome's creatures and spoil,
    the level band the wild spans, and how thickly to scatter foes, gather nodes, and guardians."""

    biome: str
    level_min: int
    level_max: int
    foe_every: int = 1  # an ambient foe every Nth wild cell (1 = one per cell, the wildlands rate)
    gather_every: int = 5  # a gather node every Nth wild cell (mirrors wildlands _GATHER_EVERY = 5)
    notable_every: int = 40  # a guardian every Nth wild cell (idx-cadenced), capped below
    notable_cap: int = 16  # at most this many guardians per region (mirrors wildlands _NOTABLE_CAP)


# --- spatial-fill helpers ------------------------------------------------------------------------


def _heightmap(w: int, h: int, seed: int) -> dict[tuple[int, int], float]:
    """A smooth, deterministic heightmap in [0, 1]: a coarse seeded grid, bilinearly interpolated so
    elevation flows (hills and valleys), not per-cell noise."""
    # This RNG seeds deterministic terrain for reproducible worlds, not security.
    rng = random.Random(seed)  # nosec B311
    step = 4
    grid = {(cx, cy): rng.random() for cx in range(w // step + 2) for cy in range(h // step + 2)}
    hm: dict[tuple[int, int], float] = {}
    for x in range(w):
        for y in range(h):
            gx, gy = x / step, y / step
            x0, y0 = int(gx), int(gy)
            fx, fy = gx - x0, gy - y0
            top = grid[(x0, y0)] * (1 - fx) + grid[(x0 + 1, y0)] * fx
            bot = grid[(x0, y0 + 1)] * (1 - fx) + grid[(x0 + 1, y0 + 1)] * fx
            hm[(x, y)] = top * (1 - fy) + bot * fy
    return hm


def _trace_river(
    hm: dict[tuple[int, int], float], w: int, h: int, source: tuple[int, int]
) -> list[tuple[int, int]]:
    """A river follows the heightmap DOWNHILL from `source`: at each step it flows to the lowest
    unseen neighbour, stopping at the map edge or a local pool. Elevation, not decoration."""
    river = [source]
    seen = {source}
    cur = source
    while True:
        x, y = cur
        if x in (0, w - 1) or y in (0, h - 1):
            break  # reached an edge of the map
        nbrs = [
            (x + dx, y + dy)
            for dx, dy in _ORTHO
            if 0 <= x + dx < w and 0 <= y + dy < h and (x + dx, y + dy) not in seen
        ]
        if not nbrs:  # pragma: no cover - a defensive guard: the river spiralled into itself
            break
        low = min(nbrs, key=lambda n: hm[n])
        if hm[low] > hm[cur]:
            break  # no downhill left: the river pools here
        river.append(low)
        seen.add(low)
        cur = low
    return river


def _terrain(
    hm: dict[tuple[int, int], float],
    river: set[tuple[int, int]],
    crossings: dict[tuple[int, int], str],
    w: int,
    h: int,
) -> dict[tuple[int, int], Cell]:
    """Read terrain from elevation: a crossing cell is its ford/bridge; a river-channel cell is
    impassable water; a high cell is a hill; a low cell is forest; the rest is open plain."""
    cells: dict[tuple[int, int], Cell] = {}
    for (x, y), height in hm.items():
        if (x, y) in crossings:
            terrain = crossings[(x, y)]
        elif (x, y) in river:
            terrain = "river"
        elif height > 0.70:
            terrain = "hill"
        elif height < 0.28:
            terrain = "forest"
        else:
            terrain = "plain"
        cells[(x, y)] = Cell(terrain, elevation=int(height * 3))
    return cells


def _road_between(
    a: tuple[int, int], b: tuple[int, int], passable: set[tuple[int, int]]
) -> list[tuple[int, int]]:
    """The shortest walkable path from a to b over passable cells (BFS). This becomes a road: a
    deliberate TRAIL through the open field, so a living world mixes routes to follow with space to
    roam. Empty if either end is a wall or no path exists."""
    if a not in passable or b not in passable:
        return []
    prev: dict[tuple[int, int], tuple[int, int] | None] = {a: None}
    queue = deque([a])
    while queue:
        cur = queue.popleft()
        if cur == b:
            break
        for dx, dy in _ORTHO:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in passable and nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    if b not in prev:
        return []
    path: list[tuple[int, int]] = []
    step: tuple[int, int] | None = b
    while step is not None:
        path.append(step)
        step = prev[step]
    return path[::-1]


def _pave_roads(cells: dict[tuple[int, int], Cell], landmarks: tuple[Landmark, ...]) -> None:
    """Lay roads between consecutive landmarks, in place: mark the path cells `road` (a river is
    crossed at its existing ford/bridge, never paved over). The open terrain around the road is
    untouched -- the trail is one path THROUGH the field."""
    passable = {
        xy for xy, c in cells.items() if c.terrain not in ("river", "water", "cliff", "wall")
    }
    anchors = [lm.at for lm in landmarks]
    for a, b in zip(anchors, anchors[1:], strict=False):
        for xy in _road_between(a, b, passable):
            c = cells[xy]
            if c.terrain in ("plain", "meadow", "forest", "hill"):
                cells[xy] = Cell("road", c.elevation)


def _reachable(exits: dict[str, dict[str, str]], start: str) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        for dest in exits[stack.pop()].values():
            if dest not in seen:
                seen.add(dest)
                stack.append(dest)
    return seen


def _declared_crossings(
    name: str, cells: dict[tuple[int, int], Cell], crossings: dict[tuple[int, int], str]
) -> list[tuple[str, str]]:
    """Every crossing edge, declared as a deliberate bottleneck so the choice gate exempts it (the
    one bridge over the river is a story feature). Harmless when a second crossing already opens a
    parallel route -- exempting a non-bridge is a no-op."""
    passable = {
        xy for xy, c in cells.items() if c.terrain not in ("river", "water", "cliff", "wall")
    }
    declared: list[tuple[str, str]] = []
    for x, y in crossings:
        for dx, dy in _ORTHO:
            bank = (x + dx, y + dy)
            if bank in passable:
                declared.append((f"{name}_{x}_{y}", f"{name}_{bank[0]}_{bank[1]}"))
    return declared


# --- the generator -------------------------------------------------------------------------------


def generate_region(spec: RegionSpec) -> Region:
    """Generate a region in two layers and judge it by every gate. Returns a Region whose `.ok` is
    True only when it is WORLD_SHAPED and every landmark is reachable."""
    if spec.width < 1 or spec.height < 1:
        raise WorldgenError(f"region {spec.name!r}: width and height must be >= 1")

    river: list[tuple[int, int]] = []
    if spec.corridor:
        cells = {(x, 0): Cell("plain") for x in range(spec.width)}  # the sabotage: a bare corridor
        declared: list[tuple[str, str]] = []
    else:
        hm = _heightmap(spec.width, spec.height, spec.seed)
        crossmap = {(x, y): kind for x, y, kind in spec.crossings}
        if spec.river_source is not None:
            river = _trace_river(hm, spec.width, spec.height, spec.river_source)
            if not crossmap and len(river) >= 3:
                # the mission layer's deliberate crossings: auto-place a ford and a bridge along the
                # river so it is crossable by construction (a river you cannot cross would wall off
                # half the region -- two crossings keep two routes, so no undeclared bottleneck).
                crossmap = {river[len(river) // 3]: "ford", river[2 * len(river) // 3]: "bridge"}
        river_set = set(river) - set(crossmap)  # a crossing overrides the river channel
        cells = _terrain(hm, river_set, crossmap, spec.width, spec.height)
        if spec.roads and len(spec.landmarks) >= 2:
            _pave_roads(cells, spec.landmarks)  # trails threading the field between living places
        declared = _declared_crossings(spec.name, cells, crossmap)

    stacks = [
        Stack(
            at=lm.at,
            room_id=f"{spec.name}_{lm.at[0]}_{lm.at[1]}_summit",
            name=f"{lm.name} Summit",
            desc=f"The peak of {lm.name}: the whole region lies open below.",
            direction="up",
            verb="climb",
            back_verb="descend",
        )
        for lm in spec.landmarks
        if lm.kind == "peak"
    ]
    rooms = build_field(spec.name, cells, stacks=stacks)

    for lm in spec.landmarks:
        rid = f"{spec.name}_{lm.at[0]}_{lm.at[1]}"
        if rid not in rooms:
            raise WorldgenError(f"landmark {lm.name!r} at {lm.at}: on impassable terrain, no room")
        rooms[rid]["name"] = lm.name
        rooms[rid]["desc"] = f"{lm.name}. {rooms[rid]['desc']}"
        rooms[rid]["landmark"] = lm.kind

    start = min(rooms)  # a stable, reproducible spawn
    exits = {rid: r["exits"] for rid, r in rooms.items()}
    report = audit_topology(exits, start=start, declared_bottlenecks=declared)
    reached = _reachable(exits, start)
    lms_reachable = all(f"{spec.name}_{lm.at[0]}_{lm.at[1]}" in reached for lm in spec.landmarks)
    return Region(spec.name, rooms, start, report, lms_reachable, tuple(river))


# --- the life layer ------------------------------------------------------------------------------


def _band(lo: int, hi: int, idx: int, span: int) -> int:
    """A level for a cell at BFS index `idx` of `span`: a linear gradient from lo (near the spawn)
    to hi (the deep field), so the wild deepens with distance. The field twin of a trail band."""
    if span <= 1:
        return lo
    return lo + (hi - lo) * min(idx, span - 1) // (span - 1)


def _cell_order(exits: dict[str, dict[str, str]], start: str) -> list[str]:
    """Every reachable cell in a stable BFS order from the spawn: closer cells first, so the wild
    deepens outward and each cell gets a distinct index (varied elite/aggression/size). It is
    deterministic (neighbours in sorted order), so the same field always fills the same way."""
    order = [start]
    seen = {start}
    queue = deque([start])
    while queue:
        for dest in sorted(exits[queue.popleft()].values()):
            if dest not in seen:
                seen.add(dest)
                order.append(dest)
                queue.append(dest)
    return order


def populate_region(region: Region, life: LifeSpec, *, origin: str | None = None) -> dict[str, Npc]:
    """Breathe life into a generated region: scatter ambient foes, gather nodes, and a handful of
    guardians across the walkable OPEN FIELD (the anchored landmarks -- towns, dungeons, peaks --
    stay safe), so a field plays like the living wilderness the trails gave. Mutates `region.rooms`
    in place to hang gather `node`s; returns the NPC records keyed by label, each `location`d on its
    cell -- the same living-content contract kernel/world/wildlands.py fills for the trails, so the
    zone's cull/forage boards keep routing once a trail flips to a field.

    The wild DEEPENS outward from `origin` (default the region's spawn): levels climb with distance,
    so the gentlest ground is at the origin. Pass the field's ENTRANCE as `origin` and a newcomer
    meets level-1 life at the door, exactly as a trail's attach point did -- the on-ramp, preserved.
    Fails loud on an empty region, a non-positive cadence, or an origin that is not a real cell."""
    if not region.rooms:
        raise WorldgenError(f"region {region.name!r}: cannot breathe life into an empty region")
    if life.foe_every < 1 or life.gather_every < 1 or life.notable_every < 1:
        raise WorldgenError(f"region {region.name!r}: life cadences must be >= 1")
    start = origin if origin is not None else region.start
    if start not in region.rooms:
        raise WorldgenError(f"region {region.name!r}: life origin {start!r} is not a cell")

    exits = {rid: r["exits"] for rid, r in region.rooms.items()}
    # the wilderness fills the open field, never the anchored sites (a town cell is no beast's den).
    wild = [rid for rid in _cell_order(exits, start) if not region.rooms[rid].get("landmark")]
    span = len(wild)
    max_notables = min(span // life.notable_every, life.notable_cap)
    materials = gatherable_materials(life.biome)

    npcs: dict[str, Npc] = {}
    seq = 0
    for idx, rid in enumerate(wild):
        level = _band(life.level_min, life.level_max, idx, span)
        if idx % life.gather_every == 0:
            region.rooms[rid]["node"] = materials[(idx // life.gather_every) % len(materials)]
        if idx and idx % life.notable_every == 0 and seq < max_notables:
            npcs[f"{region.name}_lord_{seq}"] = make_notable(life.biome, level, idx, rid, seq)
            seq += 1
        elif idx % life.foe_every == 0:
            npcs[f"{region.name}_beast_{idx}"] = make_beast(life.biome, level, idx, rid)
    return npcs
