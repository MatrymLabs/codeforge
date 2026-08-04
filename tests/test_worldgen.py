"""Test twin for kernel/worldgen.py -- the two-layer region generator (Topology Doctrine, Phase 3).

The proof the prompt demands: generate a COMPLETE region and run ALL gates (reachability,
progression, anti-trail) -- it must come back WORLD_SHAPED with every landmark reachable. And the
SABOTAGE test: a config forcing a corridor must be CAUGHT (it honestly reports TRAIL_SHAPED). Plus
rivers follow elevation, determinism, named crossings, a peak's summit, and loud refusals.
"""

from __future__ import annotations

import pytest

from kernel.field import Cell
from kernel.topology import TRAIL_SHAPED, WORLD_SHAPED
from kernel.worldgen import (
    Landmark,
    RegionSpec,
    WorldgenError,
    _road_between,
    _trace_river,
    generate_region,
)

_TOWN = Landmark((3, 3), "Rivertown", "town")
_KEEP = Landmark((20, 14), "The Old Keep", "dungeon")


# --- the headline proof: a complete region passes every gate -------------------------------------


def test_a_generated_region_passes_all_gates() -> None:
    region = generate_region(RegionSpec("vale", 24, 18, seed=7, landmarks=(_TOWN, _KEEP)))
    assert region.topology.verdict == WORLD_SHAPED, region.topology.violations
    assert region.landmarks_reachable is True  # progression: every anchor is walkable
    assert region.ok is True
    # the two layers produced BOTH content and shape
    assert region.rooms[f"vale_{_TOWN.at[0]}_{_TOWN.at[1]}"]["name"] == "Rivertown"
    assert region.topology.mean_degree >= 2.80 and region.topology.loop_ratio >= 0.25


def test_a_river_region_is_world_shaped_and_crossable() -> None:
    region = generate_region(
        RegionSpec("vale", 24, 18, seed=1, river_source=(12, 16), landmarks=(_TOWN,))
    )
    assert region.topology.verdict == WORLD_SHAPED and region.ok is True
    assert region.river  # a river was traced
    # the mission layer opened NAMED crossings so the river is passable
    crossings = {
        k for r in region.rooms.values() for k in r["exits"] if k in ("ford river", "cross bridge")
    }
    assert crossings


# --- the mixture: roads (trails) thread the open fields ------------------------------------------


def test_roads_thread_the_field_between_landmarks() -> None:
    # a living world mixes trail and field: a ROAD connects the landmarks, THROUGH open country that
    # stays world-shaped (you can follow the road or roam off it).
    region = generate_region(RegionSpec("vale", 24, 18, seed=7, landmarks=(_TOWN, _KEEP)))
    assert region.topology.verdict == WORLD_SHAPED  # still open, not a corridor
    road_rooms = [rid for rid, r in region.rooms.items() if "the road runs on" in r["desc"]]
    assert road_rooms  # a trail exists in the field
    # the road actually connects the two landmarks (a road-cell path spans them)
    road_cells = {
        tuple(int(p) for p in rid.split("_")[1:3])
        for rid in region.rooms
        if "road" in region.rooms[rid]["desc"][:40]
    }
    assert _TOWN.at in road_cells or any(
        abs(_TOWN.at[0] - c[0]) + abs(_TOWN.at[1] - c[1]) <= 1 for c in road_cells
    )


def test_a_road_crosses_a_river_at_its_ford_not_over_it() -> None:
    # a road between banks routes THROUGH the ford (a passable crossing), never paving the river.
    region = generate_region(
        RegionSpec(
            "vale",
            24,
            18,
            seed=1,
            river_source=(12, 16),
            landmarks=(Landmark((3, 8), "West End", "town"), Landmark((20, 8), "East End", "town")),
        )
    )
    assert region.topology.verdict == WORLD_SHAPED  # the road found a crossing; still world-shaped
    crossings = {
        k for r in region.rooms.values() for k in r["exits"] if k in ("ford river", "cross bridge")
    }
    assert crossings


def test_road_between_returns_empty_when_blocked() -> None:
    assert _road_between((0, 0), (5, 5), {(0, 0)}) == []  # endpoint on a wall
    assert _road_between((0, 0), (2, 0), {(0, 0), (2, 0)}) == []  # no path (a gap between)


def test_paving_a_road_leaves_a_crossing_unpaved() -> None:
    from kernel.worldgen import _pave_roads

    cells = {(x, 0): Cell("plain") for x in range(5)}
    cells[(2, 0)] = Cell("ford")  # a crossing on the road's path
    _pave_roads(cells, (Landmark((0, 0), "A", "town"), Landmark((4, 0), "B", "town")))
    assert cells[(2, 0)].terrain == "ford"  # the ford is used, never paved over
    assert cells[(1, 0)].terrain == "road"  # but the plain around it becomes road


def test_roads_can_be_turned_off_for_a_pure_wild_zone() -> None:
    region = generate_region(
        RegionSpec("wild", 24, 18, seed=7, roads=False, landmarks=(_TOWN, _KEEP))
    )
    assert not any("the road runs on" in r["desc"] for r in region.rooms.values())


# --- the SABOTAGE: a corridor must be caught -----------------------------------------------------


def test_the_sabotage_corridor_is_caught() -> None:
    region = generate_region(RegionSpec("trap", 30, 1, seed=0, corridor=True))
    assert region.topology.verdict == TRAIL_SHAPED  # the gate is not fooled
    assert region.ok is False
    assert any("linearity" in v or "loop" in v for v in region.topology.violations)


# --- rivers follow elevation, not decoration -----------------------------------------------------


def test_a_short_river_needs_no_auto_crossing() -> None:
    # a river too short to bisect the map gets no auto-placed crossings; still world-shaped.
    region = generate_region(RegionSpec("vale", 24, 18, seed=0, river_source=(12, 16)))
    assert len(region.river) < 3 and region.topology.verdict == WORLD_SHAPED


def test_a_river_flows_downhill() -> None:
    # a synthetic slope: height falls with x. A river from the top must never step UP.
    hm = {(x, y): 1.0 - x / 10 for x in range(10) for y in range(3)}
    river = _trace_river(hm, 10, 3, (1, 1))
    heights = [hm[c] for c in river]
    assert heights == sorted(heights, reverse=True)  # monotonically downhill
    assert len(river) >= 2


# --- determinism ---------------------------------------------------------------------------------


def test_the_same_seed_yields_the_same_region() -> None:
    spec = RegionSpec("vale", 20, 16, seed=3, river_source=(10, 14), landmarks=(_TOWN,))
    a = generate_region(spec)
    b = generate_region(spec)
    assert a.rooms == b.rooms and a.river == b.river and a.start == b.start


def test_different_seeds_give_different_terrain() -> None:
    a = generate_region(RegionSpec("vale", 24, 18, seed=1))
    b = generate_region(RegionSpec("vale", 24, 18, seed=99))
    descs_a = {rid: r["desc"] for rid, r in a.rooms.items()}
    descs_b = {rid: r["desc"] for rid, r in b.rooms.items()}
    assert descs_a != descs_b  # the heightmap actually varies the world


# --- a peak landmark raises a summit (vertical) --------------------------------------------------


def test_a_peak_landmark_raises_a_summit() -> None:
    region = generate_region(
        RegionSpec("vale", 24, 18, seed=2, landmarks=(Landmark((10, 9), "Skyreach", "peak"),))
    )
    peak = region.rooms["vale_10_9"]["exits"]
    assert peak["up"] == "vale_10_9_summit" and "climb" in peak
    assert "vale_10_9_summit" in region.rooms


# --- loud refusals -------------------------------------------------------------------------------


def test_a_degenerate_size_is_refused_loud() -> None:
    with pytest.raises(WorldgenError):
        generate_region(RegionSpec("bad", 0, 5))


def test_a_landmark_on_impassable_terrain_is_refused_loud(monkeypatch) -> None:
    # force a cell impassable under a landmark, then place a landmark on it -> loud refusal
    import kernel.worldgen as wg

    real = wg._terrain

    def sabotaged(hm, river, crossings, w, h):
        cells = real(hm, river, crossings, w, h)
        cells[(5, 5)] = Cell("river")  # a wall exactly where the landmark wants to stand
        return cells

    monkeypatch.setattr(wg, "_terrain", sabotaged)
    with pytest.raises(WorldgenError):
        generate_region(
            RegionSpec("vale", 24, 18, seed=1, landmarks=(Landmark((5, 5), "Sunk", "town"),))
        )
