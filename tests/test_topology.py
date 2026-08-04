"""Test twin for kernel/world/topology.py -- the anti-trail world-shape validator (Topology Doctrine
Phase 1). A world is a GRAPH WITH AREA, not a path with scenery.

The reverse-TDD contract: a known-TRAIL fixture must FAIL the gates; a known-FIELD fixture must
PASS. Plus each gate in isolation, the declared-bottleneck exemption, reachability, and configurable
thresholds.
"""

from __future__ import annotations

import pytest

from kernel.topology import (
    TRAIL_SHAPED,
    UNREACHABLE,
    WORLD_SHAPED,
    TopologyGates,
    audit_topology,
    default_gates,
    load_topology_spec,
)

# --- fixtures: the two shapes the doctrine draws a line between ----------------------------------


def _chain(n: int) -> dict[str, dict[str, str]]:
    """A pure TRAIL: r0 <-> ... <-> r(n-1). Interior rooms have exactly 2 exits (a corridor)."""
    ex: dict[str, dict[str, str]] = {f"r{i}": {} for i in range(n)}
    for i in range(n - 1):
        ex[f"r{i}"]["east"] = f"r{i + 1}"
        ex[f"r{i + 1}"]["west"] = f"r{i}"
    return ex


def _grid(w: int, h: int) -> dict[str, dict[str, str]]:
    """A FIELD: a w x h mesh -- movement flows in 4 directions, the interior full of loops."""
    ex: dict[str, dict[str, str]] = {f"c{x}_{y}": {} for x in range(w) for y in range(h)}
    for x in range(w):
        for y in range(h):
            here = f"c{x}_{y}"
            if x + 1 < w:
                ex[here]["east"] = f"c{x + 1}_{y}"
                ex[f"c{x + 1}_{y}"]["west"] = here
            if y + 1 < h:
                ex[here]["north"] = f"c{x}_{y + 1}"
                ex[f"c{x}_{y + 1}"]["south"] = here
    return ex


# --- the headline contract ----------------------------------------------------------------------


def test_a_trail_fixture_fails_the_anti_trail_gates() -> None:
    report = audit_topology(_chain(10), start="r0")
    assert report.verdict == TRAIL_SHAPED and report.ok is False
    # a corridor fails on all three measurable counts, and the report names each
    joined = " ".join(report.violations)
    assert "linearity" in joined and "loop" in joined and "degree" in joined
    assert report.linearity > 0.60 and report.mean_degree < 2.80 and report.loop_ratio < 0.25


def test_a_field_fixture_passes() -> None:
    report = audit_topology(_grid(4, 4), start="c0_0")
    assert report.verdict == WORLD_SHAPED and report.ok is True
    assert report.violations == ()
    assert report.mean_degree >= 2.80 and report.linearity <= 0.60 and report.loop_ratio >= 0.25


# --- each gate, isolated ------------------------------------------------------------------------


def test_loop_ratio_gate_a_tree_has_no_cycles() -> None:
    # A star (one hub, four dead-end spokes) is fully reachable but has ZERO loops -> trail-shaped.
    star = {
        "hub": {"n": "a", "s": "b", "e": "c", "w": "d"},
        "a": {"s": "hub"},
        "b": {"n": "hub"},
        "c": {"w": "hub"},
        "d": {"e": "hub"},
    }
    report = audit_topology(star, start="hub")
    assert report.loop_ratio == 0.0 and report.verdict == TRAIL_SHAPED
    assert any("loop" in v for v in report.violations)


def test_linearity_gate_flags_a_costume_corridor() -> None:
    report = audit_topology(_chain(20), start="r0")
    assert report.linearity > 0.60 and any("linearity" in v for v in report.violations)


def test_mean_degree_gate() -> None:
    assert audit_topology(_chain(10), start="r0").mean_degree < 2.80
    assert audit_topology(_grid(5, 5), start="c0_0").mean_degree >= 2.80


# --- the choice check + declared-bottleneck exemption -------------------------------------------


def _barbell() -> dict[str, dict[str, str]]:
    """Two fields joined by ONE bridge -- the single route between them is a real bottleneck."""
    # two 3x3 grids, prefixed L/R, joined by a bridge between a node on each side
    ex: dict[str, dict[str, str]] = {}
    for side in ("L", "R"):
        g = _grid(3, 3)
        for room, e in g.items():
            ex[side + room] = {d: side + dest for d, dest in e.items()}
    ex["Lc2_1"]["bridge"] = "Rc0_1"
    ex["Rc0_1"]["bridge"] = "Lc2_1"
    return ex


def test_an_undeclared_bottleneck_between_regions_fails_the_choice_check() -> None:
    report = audit_topology(_barbell(), start="Lc0_0")
    assert ("Lc2_1", "Rc0_1") in report.undeclared_bottlenecks or (
        "Rc0_1",
        "Lc2_1",
    ) in report.undeclared_bottlenecks
    assert any("bottleneck" in v or "route" in v for v in report.violations)


def test_a_declared_bottleneck_is_allowed() -> None:
    report = audit_topology(_barbell(), start="Lc0_0", declared_bottlenecks=[("Lc2_1", "Rc0_1")])
    assert report.undeclared_bottlenecks == ()
    assert not any("bottleneck" in v or "route" in v for v in report.violations)


def test_a_dead_end_is_not_a_bottleneck() -> None:
    # A field with a single dead-end cave: the cave's one bridge is a DELIBERATE dead end, not a
    # between-regions bottleneck, so it never trips the choice check.
    g = _grid(4, 4)
    g["c1_1"]["enter cave"] = "cave"
    g["cave"] = {"leave": "c1_1"}
    report = audit_topology(g, start="c0_0")
    assert report.undeclared_bottlenecks == () and report.verdict == WORLD_SHAPED


# --- reachability still applies ------------------------------------------------------------------


def test_an_unreachable_room_fails_reachability() -> None:
    g = _grid(3, 3)
    g["island"] = {}  # a room no exit reaches
    report = audit_topology(g, start="c0_0")
    assert report.verdict == UNREACHABLE and "island" in " ".join(report.violations)


# --- configurable thresholds (per-terrain tuning is a DECISION) ----------------------------------


def test_thresholds_are_configurable() -> None:
    # A field passes the defaults; tightening min_mean_degree past its reach flips the verdict.
    grid = _grid(4, 4)
    assert audit_topology(grid, start="c0_0").verdict == WORLD_SHAPED
    strict = TopologyGates(min_mean_degree=3.9)  # a 4x4 grid can't average 3.9
    assert audit_topology(grid, start="c0_0", gates=strict).verdict == TRAIL_SHAPED


def test_default_gates_match_the_doctrine() -> None:
    g = default_gates()
    assert g.max_linearity == 0.60 and g.min_mean_degree == 2.80 and g.min_loop_ratio == 0.25


def test_the_topology_spec_loads_as_data() -> None:
    # The doctrine ships as DATA (directions, terrain+passability, backings, gates); it must parse
    # and carry the gate thresholds the validator defaults to.
    spec = load_topology_spec()
    assert "cardinal" in spec["directions"] and "intercardinal" in spec["directions"]
    assert "river" in spec["terrain"] and spec["terrain"]["river"]["passable"] is False
    assert spec["gates"]["min_loop_ratio"] == 0.25


# --- hostile / degenerate ------------------------------------------------------------------------


def test_an_empty_graph_is_refused_loud() -> None:
    with pytest.raises(ValueError):
        audit_topology({}, start="nowhere")


def test_a_dangling_exit_is_refused_loud() -> None:
    with pytest.raises(ValueError):
        audit_topology({"a": {"east": "ghost"}}, start="a")


def test_a_start_not_in_the_graph_is_refused_loud() -> None:
    with pytest.raises(ValueError):
        audit_topology(_grid(2, 2), start="c9_9")


def test_a_self_loop_exit_is_not_an_edge() -> None:
    # A room with an exit to ITSELF (a 'wait' loop) adds no undirected edge and is not a bridge.
    g = _grid(4, 4)
    g["c1_1"]["wait"] = "c1_1"
    report = audit_topology(g, start="c0_0")
    assert report.verdict == WORLD_SHAPED  # the self-loop does not perturb the field's shape


def test_the_spec_fails_loud_when_missing(tmp_path) -> None:
    with pytest.raises(ValueError):
        load_topology_spec(tmp_path / "nope.yaml")


def test_the_spec_fails_loud_when_malformed(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("terrain: {}\n")  # a mapping, but missing 'gates'
    with pytest.raises(ValueError):
        load_topology_spec(bad)
