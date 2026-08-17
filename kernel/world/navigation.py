"""CARD: navigation -- the world as a graph: shortest room paths + reachability, native-accelerated.

CodeForge's world is a directed graph: rooms are nodes, exits are edges. This card answers the
spatial questions -- the shortest path between two rooms (fewest exits), and how much of the world
is reachable from a point (a connectivity audit at million-room scale).

It is the first organ of the polyglot "assimilation" build, and it is **Python-first with a native
accelerator**: when the Rust kernel `codeforge_nav` (native/codeforge_nav, built via maturin) is
installed, its `NavGraph` is used; otherwise an identical pure-Python `NavGraph` runs. The two are
pinned to identical behaviour by a parity test (tests/test_navigation.py), so the game never
hard-depends on the compiled build -- Rust where it earns its place (bulk graph traversal at scale),
behind a narrow FFI, with a fallback and evidence (benchmarks/bench_nav.py).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from typing import Protocol


class NavGraphLike(Protocol):
    """The interface both backends satisfy -- the contract that keeps the Rust kernel and the
    Python fallback interchangeable (and that the parity test enforces)."""

    def __init__(self, edges: Iterable[tuple[str, str]]) -> None: ...
    def node_count(self) -> int: ...
    def path(self, src: str, dst: str) -> list[str] | None: ...
    def distance(self, src: str, dst: str) -> int | None: ...
    def reachable_count(self, src: str) -> int | None: ...


class PyNavGraph:
    """A directed room-graph with BFS pathfinding + reachability -- the pure-Python reference.

    Labels are interned to dense integer indices at construction (exactly as the Rust kernel does),
    so BFS neighbour order matches the native implementation and the two return identical paths."""

    def __init__(self, edges: Iterable[tuple[str, str]]) -> None:
        self._ids: dict[str, int] = {}
        self._labels: list[str] = []
        self._adj: list[list[int]] = []
        for frm, to in edges:
            a = self._intern(frm)
            b = self._intern(to)
            self._adj[a].append(b)

    def _intern(self, label: str) -> int:
        idx = self._ids.get(label)
        if idx is None:
            idx = len(self._labels)
            self._ids[label] = idx
            self._labels.append(label)
            self._adj.append([])
        return idx

    def node_count(self) -> int:
        """Number of distinct rooms in the graph."""
        return len(self._labels)

    def path(self, src: str, dst: str) -> list[str] | None:
        """Shortest path src..dst as room labels, inclusive; None if unknown or unreachable."""
        source = self._ids.get(src)
        dest = self._ids.get(dst)
        if source is None or dest is None:
            return None
        if source == dest:
            return [src]
        prev: dict[int, int] = {source: source}
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for v in self._adj[u]:
                if v not in prev:
                    prev[v] = u
                    if v == dest:
                        out = [dest]
                        cur = dest
                        while cur != source:
                            cur = prev[cur]
                            out.append(cur)
                        out.reverse()
                        return [self._labels[i] for i in out]
                    queue.append(v)
        return None

    def distance(self, src: str, dst: str) -> int | None:
        """Number of exits on the shortest path, or None if unreachable/unknown."""
        found = self.path(src, dst)
        return None if found is None else len(found) - 1

    def reachable_count(self, src: str) -> int | None:
        """How many rooms are reachable from src (inclusive); None if src is unknown. Compare to
        node_count() for a connectivity audit."""
        source = self._ids.get(src)
        if source is None:
            return None
        seen = {source}
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for v in self._adj[u]:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        return len(seen)


NavGraph: type[NavGraphLike]
try:  # pragma: no cover -- the branch taken depends on whether the native kernel is installed
    from codeforge_nav import NavGraph as _RustNavGraph  # native/codeforge_nav via maturin

    NavGraph = _RustNavGraph
    BACKEND = "rust"
except ImportError:  # pragma: no cover -- fallback branch (taken only when the kernel is absent)
    NavGraph = PyNavGraph
    BACKEND = "python"


def world_edges() -> list[tuple[str, str]]:
    """Every exit in the live world as (from_room, to_room) directed edges."""
    from kernel.world.world import WORLD

    return [
        (label, dest) for label, room in WORLD.items() for dest in room.get("exits", {}).values()
    ]


_cached_graph: NavGraphLike | None = None
_cached_world_key: tuple[int, int] = (-1, -1)


def reindex_navgraph() -> None:
    """Drop the cached world NavGraph so the next lookup rebuilds it. Production builds WORLD once
    at boot (delves and all) and never changes it, so this is only needed after mutating WORLD in
    place at an unchanged size -- e.g. a test -- which the automatic size check cannot see."""
    global _cached_world_key  # noqa: PLW0603
    _cached_world_key = (-1, -1)


def world_navgraph() -> NavGraphLike:
    """A NavGraph over the live world -- native if the Rust kernel is built, else pure-Python.

    CACHED: building it scans every room and exit (~130ms at aethryn's ~53k-room scale) and the
    `route` command asks for it on every call, so a fresh build per route added ~130ms of latency
    each time. WORLD is assembled once at boot and does not change during play, so the graph is
    built once and reused. Invalidation is keyed on WORLD's identity and size: swapping it (a test)
    or growing it in place rebuilds on the next call; `reindex_navgraph` forces it."""
    global _cached_graph, _cached_world_key  # noqa: PLW0603
    from kernel.world.world import WORLD

    key = (id(WORLD), len(WORLD))
    if _cached_graph is None or _cached_world_key != key:
        _cached_graph = NavGraph(world_edges())
        _cached_world_key = key
    return _cached_graph
