"""Test twin for kernel/world/navigation.py -- the world-graph kernel (Python + Rust parity).

The pure-Python `PyNavGraph` is the reference and is always tested. When the native Rust kernel
`codeforge_nav` is built (native/codeforge_nav via maturin), a PARITY test pins it to identical
behaviour -- same paths, same reachability -- so the accelerator can never silently diverge from the
fallback. When the kernel is absent (CI without the native build), that parity test skips and the
fallback stands alone; the game is green either way.
"""

from __future__ import annotations

import importlib.util

import pytest

from kernel.world import navigation
from kernel.world.navigation import BACKEND, NavGraph, PyNavGraph

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


def test_world_navgraph_is_cached_between_calls():
    # The ~130ms build must not repeat on every `route`: a static world returns the same graph.
    navigation.reindex_navgraph()  # start cold (another test may have swapped WORLD)
    first = navigation.world_navgraph()
    assert navigation.world_navgraph() is first  # reused, not rebuilt


def test_world_navgraph_rebuilds_when_the_world_is_swapped(monkeypatch):
    import kernel.world.world as world_mod  # noqa: PLC0415

    first = navigation.world_navgraph()
    mini = {
        "a": {"name": "A", "desc": "", "exits": {"north": "b"}},
        "b": {"name": "B", "desc": "", "exits": {}},
    }
    monkeypatch.setattr(world_mod, "WORLD", mini)
    swapped = navigation.world_navgraph()
    assert swapped is not first  # a different world rebuilds the graph
    assert swapped.node_count() == 2  # over the swapped world, not the cached one


# --- Rust <-> Python parity (skips when the native kernel is not built) -------------------------
@pytest.mark.skipif(not _HAS_RUST, reason="native codeforge_nav not built (maturin develop)")
def test_rust_matches_the_python_reference():
    import random  # noqa: PLC0415

    import codeforge_nav  # noqa: PLC0415

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
    import forge  # noqa: PLC0415
    from kernel.world.session import Session  # noqa: PLC0415
    from kernel.world.world import START_ROOM  # noqa: PLC0415

    out = forge.handle_command(Session(player_id="walker", location=START_ROOM), "route")
    assert "Route to where" in out  # the verb is wired into the engine tick


def test_route_finds_a_path_between_two_real_rooms():
    import forge  # noqa: PLC0415
    from kernel.world.session import Session  # noqa: PLC0415
    from kernel.world.world import WORLD  # noqa: PLC0415

    start = next(r for r, room in WORLD.items() if room.get("exits"))
    dest = WORLD[start]["exits"][next(iter(WORLD[start]["exits"]))]  # a direct neighbour
    out = forge.handle_command(Session(player_id="walker", location=start), f"route {dest}")
    assert f"Route to {dest}" in out and "1 steps" in out


# --- route command edge cases (over a small monkeypatched world) --------------------------------
def _mini_world(monkeypatch):
    import kernel.world.world as world_mod  # noqa: PLC0415

    world = {
        "a": {"name": "A", "desc": "", "exits": {"north": "b"}},
        "b": {"name": "B", "desc": "", "exits": {}},  # a sink: no path back to a
    }
    monkeypatch.setattr(world_mod, "WORLD", world)


def test_route_refuses_an_unknown_target(monkeypatch):
    from kernel.world.session import Session  # noqa: PLC0415
    from kernel.world.travel import route  # noqa: PLC0415

    _mini_world(monkeypatch)
    assert "no room called 'zzz'" in route(Session(player_id="w", location="a"), "zzz")


def test_route_notices_you_are_already_there(monkeypatch):
    from kernel.world.session import Session  # noqa: PLC0415
    from kernel.world.travel import route  # noqa: PLC0415

    _mini_world(monkeypatch)
    assert "already there" in route(Session(player_id="w", location="a"), "a")


def test_route_reports_no_path_on_foot(monkeypatch):
    from kernel.world.session import Session  # noqa: PLC0415
    from kernel.world.travel import route  # noqa: PLC0415

    _mini_world(monkeypatch)
    # b -> a has no directed path (a->b only)
    assert "no route on foot" in route(Session(player_id="w", location="b"), "a")


def test_route_needs_a_destination(monkeypatch):
    from kernel.world.session import Session  # noqa: PLC0415
    from kernel.world.travel import route  # noqa: PLC0415

    _mini_world(monkeypatch)
    assert "Route to where" in route(Session(player_id="w", location="a"), "")
