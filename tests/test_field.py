"""Test twin for kernel/field.py -- the coordinate-backed FIELD backing (Topology Doctrine Phase 2).

The proof the prompt demands: a 20x20 open field with a river crossing it, ONE ford and ONE bridge,
hills with up/down (a summit), and named exits -- walkable in all applicable directions, and the
topology validator green (WORLD_SHAPED). Plus the movement rules in isolation and the loud refusals.
"""

from __future__ import annotations

import pytest

from kernel.field import Cell, FieldError, Stack, build_field
from kernel.topology import WORLD_SHAPED, audit_topology

_W = _H = 20
_RIVER_X = 10
_FORD = (10, 5)
_BRIDGE = (10, 15)
_PEAK = (17, 17)
_SUMMIT = "proof_summit"


def _demo_cells() -> dict[tuple[int, int], Cell]:
    """A 20x20 plain, split by a river with one ford and one bridge; hills in a corner."""
    cells: dict[tuple[int, int], Cell] = {}
    for x in range(_W):
        for y in range(_H):
            if x == _RIVER_X:
                terrain = "river"
            elif 15 <= x <= 19 and 15 <= y <= 19:
                terrain = "hill"
            else:
                terrain = "plain"
            cells[(x, y)] = Cell(terrain, elevation=1 if terrain == "hill" else 0)
    cells[_FORD] = Cell("ford")
    cells[_BRIDGE] = Cell("bridge")
    return cells


def _demo_field() -> dict[str, dict]:
    stack = Stack(
        at=_PEAK,
        room_id=_SUMMIT,
        name="The Windswept Summit",
        desc="The whole field lies open below; the wind is loud and the air thin.",
        direction="up",
        verb="climb",
        back_verb="descend",
    )
    return build_field("proof", _demo_cells(), stacks=[stack])


def _exits(rooms: dict[str, dict], x: int, y: int) -> dict[str, str]:
    return rooms[f"proof_{x}_{y}"]["exits"]


# --- the headline proof: a world-shaped field ----------------------------------------------------


def test_the_proof_field_validates_world_shaped() -> None:
    rooms = _demo_field()
    exits = {rid: r["exits"] for rid, r in rooms.items()}
    report = audit_topology(exits, start="proof_0_0")
    assert report.verdict == WORLD_SHAPED, report.violations
    # an open field branches, loops, and is not a corridor
    assert report.mean_degree >= 2.80 and report.linearity <= 0.60 and report.loop_ratio >= 0.25


def test_the_river_has_exactly_two_crossings() -> None:
    rooms = _demo_field()
    # the ford and the bridge exist as rooms; every other river cell is a GAP (no room = a wall)
    assert "proof_10_5" in rooms and "proof_10_15" in rooms
    assert not any(f"proof_10_{y}" in rooms for y in range(_H) if y not in (5, 15))


# --- movement rules in isolation -----------------------------------------------------------------


def test_an_interior_cell_is_walkable_in_all_eight_directions() -> None:
    e = _exits(_demo_field(), 3, 3)  # deep in the western plain
    for d in ("north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"):
        assert d in e, f"missing {d}"


def test_a_river_cell_blocks_the_crossing_except_at_a_ford_or_bridge() -> None:
    rooms = _demo_field()
    # west bank at a plain-river boundary: no way EAST (the river is a wall)
    assert "east" not in _exits(rooms, 9, 7)
    # west bank at the ford: EAST works, and so does the NAMED crossing
    assert _exits(rooms, 9, 5)["east"] == "proof_10_5"
    assert _exits(rooms, 9, 5)["ford river"] == "proof_10_5"
    # and you can walk clean across: 9,5 -> ford -> 11,5
    assert _exits(rooms, 10, 5)["east"] == "proof_11_5"


def test_the_bridge_is_a_named_crossing() -> None:
    assert _exits(_demo_field(), 9, 15)["cross bridge"] == "proof_10_15"


def test_no_corner_cutting_across_the_river() -> None:
    # a diagonal that would cut past the river corner is refused (a wall is not passable diagonally)
    rooms = _demo_field()
    assert "northeast" not in _exits(rooms, 9, 4)  # NE would cut across the river column at x=10


def test_the_summit_is_reachable_up_and_down() -> None:
    rooms = _demo_field()
    peak = _exits(rooms, *_PEAK)
    assert peak["up"] == _SUMMIT and peak["climb"] == _SUMMIT
    summit = rooms[_SUMMIT]["exits"]
    assert summit["down"] == f"proof_{_PEAK[0]}_{_PEAK[1]}" and summit["descend"].startswith(
        "proof_"
    )


def test_the_full_direction_vocabulary_appears() -> None:
    rooms = _demo_field()
    keys = {k for r in rooms.values() for k in r["exits"]}
    assert {"north", "south", "east", "west"} <= keys  # cardinal
    assert {"northeast", "northwest", "southeast", "southwest"} <= keys  # intercardinal
    assert {"up", "down"} <= keys  # vertical
    assert {"ford river", "cross bridge", "climb", "descend"} <= keys  # named


def test_a_road_is_described_as_followable() -> None:
    # a road strip through a field: the road cell says where the trail runs on, so it is followable
    cells = {(x, 0): Cell("plain") for x in range(5)}
    cells[(1, 0)] = cells[(2, 0)] = cells[(3, 0)] = Cell("road")
    rooms = build_field("r", cells)
    assert "the road runs on" in rooms["r_2_0"]["desc"]


def test_descriptions_are_terrain_driven_not_identical() -> None:
    rooms = _demo_field()
    # a field cell beside the river mentions the water; a deep-plain cell does not
    assert "water" in rooms["proof_9_7"]["desc"]
    assert "water" not in rooms["proof_3_3"]["desc"]


# --- loud refusals -------------------------------------------------------------------------------


def test_an_empty_field_is_refused_loud() -> None:
    with pytest.raises(FieldError):
        build_field("empty", {})


def test_an_unknown_terrain_is_refused_loud() -> None:
    with pytest.raises(FieldError):
        build_field("bad", {(0, 0): Cell("lava")})


def test_a_stack_on_an_impassable_cell_is_refused_loud() -> None:
    cells = {(0, 0): Cell("plain"), (1, 0): Cell("river")}
    with pytest.raises(FieldError):
        build_field("s", cells, stacks=[Stack(at=(1, 0), room_id="x", name="X", desc="x")])


def test_a_stack_needs_a_valid_direction() -> None:
    with pytest.raises(FieldError):
        build_field(
            "s",
            {(0, 0): Cell("plain")},
            stacks=[Stack(at=(0, 0), room_id="x", name="X", desc="x", direction="sideways")],
        )
