"""CARD: topology -- judge whether a world graph is WORLD-SHAPED (a graph with area) or TRAIL-SHAPED
(a path with scenery). The anti-trail gate of the World Topology Doctrine.

"A world is a graph with area, not a path with scenery." A generated or hand-built zone must earn a
verdict against measurable gates: not too linear (few rooms with exactly two exits), enough exit
degree (open terrain branches), enough loops (rooms lie on cycles, so there is more than one route),
and no UNDECLARED bottleneck between two substantial areas (the one bridge over the river is allowed
only when a caller declares it; a leaf-spur to a dead-end cave is a deliberate dead end, never a
bottleneck). Reachability still applies -- a world-shaped map must be fully walkable from its start.

  * `audit_topology(exits, *, start, gates=, declared_bottlenecks=)` -> a TopologyReport verdict:
    WORLD_SHAPED (reachable AND every gate holds), TRAIL_SHAPED (reachable but a gate fails), or
    UNREACHABLE (a room the start cannot reach). Fails loud on an empty graph or a dangling exit.

The thresholds are the doctrine's defaults (see content/world/topology.yaml); tune per terrain via
a TopologyGates override (a DECISION). Metrics: linearity + mean degree read the EXITS (out-degree,
what the player uses); loops + bottlenecks read the undirected walk graph (a cycle is undirected).
Verdicts, not booleans. Status: PROTOTYPED (World Topology Doctrine, Phase 1).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent  # kernel/world/ -> repo root
_SPEC_PATH = _ROOT / "content" / "world" / "topology.yaml"

# --- verdict words (a distinct vocabulary: "is this a world, or a trail?") -----------------------
WORLD_SHAPED = "world_shaped"  # reachable AND every anti-trail gate holds
TRAIL_SHAPED = "trail_shaped"  # reachable, but a corridor/tree/bottleneck gate fails
UNREACHABLE = "unreachable"  # a room the start cannot reach: not even a whole world yet

Exits = dict[str, dict[str, str]]  # room -> {direction: destination room}


class TopologyError(ValueError):
    """A graph that cannot be judged (empty, or an exit naming no room). Fails loud."""


@dataclass(frozen=True)
class TopologyGates:
    """The anti-trail thresholds. Defaults are the doctrine's; an override is a DECISION."""

    max_linearity: float = (
        0.60  # > this fraction of rooms with EXACTLY 2 exits = a costume corridor
    )
    min_mean_degree: float = 2.80  # open terrain should branch (4-8); this is the floor
    min_loop_ratio: float = 0.25  # < this fraction of rooms on a cycle = a tree, not a world
    require_choice: bool = True  # an undeclared between-regions bridge fails the choice check


def default_gates() -> TopologyGates:
    """The doctrine's default thresholds (also mirrored as data in content/world/topology.yaml)."""
    return TopologyGates()


def load_topology_spec(path: Path | None = None) -> dict[str, Any]:
    """The World Topology Doctrine as data: directions, terrain + passability, zone backings, gates,
    and the two-layer generation design. Fails loud if the spec is missing or malformed."""
    import yaml  # a real dep (loaders use it); imported here to keep the module light

    spec_path = path or _SPEC_PATH
    if not spec_path.exists():
        raise TopologyError(f"topology spec not found at {spec_path}")
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "gates" not in data or "terrain" not in data:
        raise TopologyError("topology spec must be a mapping with 'gates' and 'terrain'")
    return data


@dataclass(frozen=True)
class TopologyReport:
    """The honest verdict on a world graph's shape, with the metrics that decided it."""

    verdict: str
    rooms: int = 0
    mean_degree: float = 0.0  # mean exits per room (out-degree)
    linearity: float = 0.0  # fraction of rooms with EXACTLY two exits
    loop_ratio: float = 0.0  # fraction of rooms lying on a cycle
    undeclared_bottlenecks: tuple[tuple[str, str], ...] = ()  # between-regions single routes
    violations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.verdict == WORLD_SHAPED


def _validate(exits: Exits, start: str) -> None:
    if not exits:
        raise TopologyError("an empty graph has no topology to judge")
    if start not in exits:
        raise TopologyError(f"start room {start!r} is not in the graph")
    for room, outs in exits.items():
        for direction, dest in outs.items():
            if dest not in exits:
                raise TopologyError(
                    f"room {room!r} exit {direction!r} -> {dest!r}: names no room (dangling exit)"
                )


def _unreached(exits: Exits, start: str) -> list[str]:
    """Rooms the start cannot reach by walking directed exits (BFS). Empty == fully reachable."""
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        for dest in exits[queue.popleft()].values():
            if dest not in seen:
                seen.add(dest)
                queue.append(dest)
    return sorted(set(exits) - seen)


def _undirected(exits: Exits) -> dict[str, set[str]]:
    """The undirected walk graph: an edge between u and v if either can reach the other directly."""
    adj: dict[str, set[str]] = {room: set() for room in exits}
    for room, outs in exits.items():
        for dest in outs.values():
            if dest != room:  # a self-loop is no edge
                adj[room].add(dest)
                adj[dest].add(room)
    return adj


def _bridges(adj: dict[str, set[str]]) -> set[frozenset[str]]:
    """Every bridge edge (removing it disconnects the graph), by iterative Tarjan low-link. A bridge
    lies on no cycle; a non-bridge edge lies on at least one."""
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    bridges: set[frozenset[str]] = set()
    timer = 0
    for root in adj:  # noqa: PLC0206
        if root in disc:
            continue
        # iterative DFS; the stack holds (node, parent, iterator over neighbours)
        stack: list[tuple[str, str | None, Any]] = [(root, None, iter(adj[root]))]
        disc[root] = low[root] = timer
        timer += 1
        while stack:
            node, parent, it = stack[-1]
            advanced = False
            for nb in it:
                if nb == parent:
                    continue
                if nb not in disc:
                    disc[nb] = low[nb] = timer
                    timer += 1
                    stack.append((nb, node, iter(adj[nb])))
                    advanced = True
                    break
                low[node] = min(low[node], disc[nb])  # back edge
            if not advanced:
                stack.pop()
                if stack:
                    p = stack[-1][0]
                    low[p] = min(low[p], low[node])
                    if low[node] > disc[p]:
                        bridges.add(frozenset({p, node}))
    return bridges


def audit_topology(
    exits: Exits,
    *,
    start: str,
    gates: TopologyGates | None = None,
    declared_bottlenecks: Iterable[tuple[str, str]] = (),
) -> TopologyReport:
    """Judge a world graph. `exits` maps room -> {direction: destination}; `start` is the spawn used
    for reachability. `declared_bottlenecks` are deliberate single routes (pairs of room ids) exempt
    from the choice check. Returns a verdict: UNREACHABLE / TRAIL_SHAPED / WORLD_SHAPED."""
    gates = gates or default_gates()
    _validate(exits, start)
    declared = {frozenset(pair) for pair in declared_bottlenecks}

    n = len(exits)
    degrees = [len(outs) for outs in exits.values()]
    mean_degree = sum(degrees) / n
    linearity = sum(1 for d in degrees if d == 2) / n  # noqa: PLR2004

    adj = _undirected(exits)
    bridges = _bridges(adj)
    # a room is on a cycle iff it has at least one NON-bridge incident edge
    on_cycle = {
        room
        for room, nbrs in adj.items()
        if any(frozenset({room, nb}) not in bridges for nb in nbrs)
    }
    loop_ratio = len(on_cycle) / n
    # a between-regions bottleneck: a bridge whose BOTH endpoints are substantial (undirected degree
    # >= 2), so it separates two real areas -- not a leaf-spur to a deliberate dead end.
    undeclared: list[tuple[str, str]] = []
    for edge in bridges:
        if all(len(adj[node]) >= 2 for node in edge) and edge not in declared:  # noqa: PLR2004
            a, b = sorted(edge)
            undeclared.append((a, b))
    undeclared.sort()

    # reachability first: an unreachable room is not even a whole world yet.
    unreached = _unreached(exits, start)
    if unreached:
        return TopologyReport(
            UNREACHABLE,
            n,
            round(mean_degree, 3),
            round(linearity, 3),
            round(loop_ratio, 3),
            tuple(undeclared),
            (f"{len(unreached)} room(s) unreachable from {start!r}: {', '.join(unreached[:5])}",),
        )

    violations: list[str] = []
    if linearity > gates.max_linearity:
        violations.append(
            f"linearity {linearity:.0%} of rooms have exactly 2 exits (a corridor wearing a "
            f"costume; gate <= {gates.max_linearity:.0%})"
        )
    if mean_degree < gates.min_mean_degree:
        violations.append(
            f"mean exit degree {mean_degree:.2f} is below the open-terrain floor "
            f"{gates.min_mean_degree:.2f} (the world does not branch)"
        )
    if loop_ratio < gates.min_loop_ratio:
        violations.append(
            f"loop ratio {loop_ratio:.0%} of rooms lie on a cycle (a tree, not a world; gate "
            f">= {gates.min_loop_ratio:.0%})"
        )
    if gates.require_choice and undeclared:
        named = ", ".join(f"{a}<->{b}" for a, b in undeclared[:3])
        violations.append(
            f"{len(undeclared)} undeclared bottleneck(s) -- a single route between two areas "
            f"({named}); declare it a deliberate feature or open a second route"
        )

    verdict = WORLD_SHAPED if not violations else TRAIL_SHAPED
    return TopologyReport(
        verdict,
        n,
        round(mean_degree, 3),
        round(linearity, 3),
        round(loop_ratio, 3),
        tuple(undeclared),
        tuple(violations),
    )
