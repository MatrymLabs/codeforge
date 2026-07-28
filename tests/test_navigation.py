"""Test twin for parts/world/navigation.py -- the world-graph kernel (Python + Rust parity).

The pure-Python `PyNavGraph` is the reference and is always tested. When the native Rust kernel
`codeforge_nav` is built (native/codeforge_nav via maturin), a PARITY test pins it to identical
behaviour -- same paths, same reachability -- so the accelerator can never silently diverge from the
fallback. When the kernel is absent (CI without the native build), that parity test skips and the
fallback stands alone; the game is green either way.
"""

from __future__ import annotations

import importlib.util

import pytest

from parts.world import navigation
from parts.world.navigation import BACKEND, NavGraph, PyNavGraph

_HAS_RUST = importlib.util.find_spec("codeforge_nav") is not None

# A directed diamond with a shortcut: a->b->d, a->c->d, and a direct a->d.
_DIAMOND = [("a", "b"), ("b", "d"), ("a", "c"), ("c", "d"), ("a", "d")]


# --- the pure-Python reference (always runs) ---------------------------------------------------
def test_shortest_path_is_the_fewest_exits():
    g = PyNavGraph(_DIAMOND)
    assert g.path("a", "d") == ["a", "d"]  # the direct edge, one hop
    assert g.distance("a", "d") == 1
    assert g.path("a", "a") == ["a"] and g.distance("a", "a") == 0


def test_edges_are_directed():
    g = PyNavGraph([("a", "b")])
    assert g.path("a", "b") == ["a", "b"]
    assert g.path("b", "a") is None  # no reverse edge


def test_unknown_rooms_and_unreachable_are_none():
    g = PyNavGraph(_DIAMOND)
    assert g.path("a", "zzz") is None
    assert g.distance("zzz", "a") is None
    assert g.reachable_count("zzz") is None


def test_reachability_counts_the_component():
    g = PyNavGraph(_DIAMOND)
    assert g.node_count() == 4
    assert g.reachable_count("a") == 4  # a reaches b, c, d
    assert g.reachable_count("d") == 1  # a sink reaches only itself


def test_a_longer_path_when_no_shortcut_exists():
    g = PyNavGraph([("a", "b"), ("b", "c"), ("a", "c"), ("c", "d")])
    assert g.path("a", "d") == ["a", "c", "d"]  # a->c->d, two hops
    assert g.distance("a", "d") == 2


# --- backend selection + live world graph ------------------------------------------------------
def test_backend_is_reported_and_usable():
    assert BACKEND in ("rust", "python")
    g = NavGraph(_DIAMOND)  # the active backend, whichever it is
    assert g.node_count() == 4 and g.path("a", "d") == ["a", "d"]


def test_world_navgraph_builds_from_the_live_world():
    edges = navigation.world_edges()
    assert edges and all(isinstance(a, str) and isinstance(b, str) for a, b in edges)
    graph = navigation.world_navgraph()
    assert graph.node_count() > 0


# --- Rust <-> Python parity (skips when the native kernel is not built) -------------------------
@pytest.mark.skipif(not _HAS_RUST, reason="native codeforge_nav not built (maturin develop)")
def test_rust_matches_the_python_reference():
    import random

    import codeforge_nav  # type: ignore[import-untyped]

    rng = random.Random(1234)
    n = 4000
    edges: list[tuple[str, str]] = []
    for i in range(n - 1):
        edges.append((f"r{i}", f"r{i + 1}"))  # a spine so most pairs are reachable
        if i % 4 == 0:
            edges.append((f"r{i}", f"r{rng.randint(0, n - 1)}"))  # cross-links

    rust = codeforge_nav.NavGraph(edges)
    ref = PyNavGraph(edges)
    assert rust.node_count() == ref.node_count()
    assert rust.reachable_count("r0") == ref.reachable_count("r0")
    for _ in range(500):
        a, b = f"r{rng.randint(0, n - 1)}", f"r{rng.randint(0, n - 1)}"
        assert rust.path(a, b) == ref.path(a, b)
        assert rust.distance(a, b) == ref.distance(a, b)


def test_route_command_is_reachable_through_the_tick():
    import forge
    from parts.world.session import Session
    from parts.world.world import START_ROOM

    out = forge.handle_command(Session(player_id="walker", location=START_ROOM), "route")
    assert "Route to where" in out  # the verb is wired into the engine tick


def test_route_finds_a_path_between_two_real_rooms():
    import forge
    from parts.world.session import Session
    from parts.world.world import WORLD

    start = next(r for r, room in WORLD.items() if room.get("exits"))
    dest = WORLD[start]["exits"][next(iter(WORLD[start]["exits"]))]  # a direct neighbour
    out = forge.handle_command(Session(player_id="walker", location=start), f"route {dest}")
    assert f"Route to {dest}" in out and "1 steps" in out
