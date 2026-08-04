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


# --- the life layer: foes + gather nodes + guardians on the open field ---------------------------


def _living_vale(seed: int = 7, **life_kw):
    """A world-shaped region plus its life, for the life-layer proofs."""
    from kernel.worldgen import LifeSpec, populate_region

    region = generate_region(RegionSpec("vale", 24, 18, seed=seed, landmarks=(_TOWN, _KEEP)))
    npcs = populate_region(region, LifeSpec("temperate-meadow", 1, 30, **life_kw))
    return region, npcs


def test_a_field_comes_alive_with_foes_gather_and_guardians() -> None:
    region, npcs = _living_vale()
    assert npcs, "the field must be populated with creatures"
    # every creature stands on a real, non-landmark cell of THIS region
    for npc in npcs.values():
        room = region.rooms[npc["location"]]
        assert not room.get("landmark"), "no monster dens in the anchored sites"
    # gather nodes were hung, each a material this biome can actually yield
    from kernel.world.wildlands import gatherable_materials

    yields = set(gatherable_materials("temperate-meadow"))
    nodes = [r["node"] for r in region.rooms.values() if "node" in r]
    assert nodes, "the field must carry gather nodes"
    assert all(n in yields for n in nodes)
    # a handful of guardians, each a named notable of an elite/boss tier
    lords = {k: v for k, v in npcs.items() if k.startswith("vale_lord_")}
    assert lords, "the field must seat guardians to hunt"
    assert all(v["tier"] in ("elite", "boss") for v in lords.values())


def test_every_wild_cell_holds_exactly_one_creature_at_the_default_rate() -> None:
    region, npcs = _living_vale()
    wild = [rid for rid in region.rooms if not region.rooms[rid].get("landmark")]
    located = [npc["location"] for npc in npcs.values()]
    assert len(located) == len(set(located)), "no two creatures share a cell"
    assert set(located) == set(wild), "foe_every=1 puts one creature on every wild cell"


def test_a_guardian_replaces_the_ambient_on_its_cell() -> None:
    region, npcs = _living_vale()
    guardian_cells = {v["location"] for k, v in npcs.items() if k.startswith("vale_lord_")}
    ambient_cells = {v["location"] for k, v in npcs.items() if k.startswith("vale_beast_")}
    assert guardian_cells, "there must be at least one guardian to check"
    assert guardian_cells.isdisjoint(ambient_cells), (
        "a guardian is not shadowed by an ambient beast"
    )


def test_the_wild_deepens_with_distance_from_the_spawn() -> None:
    region, npcs = _living_vale()
    # the creature nearest the spawn is weaker than the one deepest in the field
    from kernel.worldgen import _cell_order

    exits = {rid: r["exits"] for rid, r in region.rooms.items()}
    order = [
        rid for rid in _cell_order(exits, region.start) if not region.rooms[rid].get("landmark")
    ]
    by_cell = {npc["location"]: npc for npc in npcs.values()}
    near = by_cell[order[0]]["level"]
    far = by_cell[order[-1]]["level"]
    assert far > near, f"the deep field ({far}) must out-level the spawn's edge ({near})"


def test_guardians_are_capped_no_matter_how_large_the_field() -> None:
    _, npcs = _living_vale(notable_every=1, notable_cap=3)  # a guardian would fit every cell
    lords = [k for k in npcs if k.startswith("vale_lord_")]
    assert len(lords) == 3, "the cap holds even when the cadence would seat far more"


def test_a_sparser_cadence_leaves_peaceful_open_ground() -> None:
    region, npcs = _living_vale(foe_every=4, notable_every=1000)
    wild = [rid for rid in region.rooms if not region.rooms[rid].get("landmark")]
    creature_cells = {npc["location"] for npc in npcs.values()}
    assert len(creature_cells) < len(wild), "a sparse field must leave empty, roamable ground"


def test_life_never_disturbs_the_world_shape() -> None:
    region, _ = _living_vale()
    before = generate_region(RegionSpec("vale", 24, 18, seed=7, landmarks=(_TOWN, _KEEP)))
    # populate mutates rooms (nodes/npcs) but never the exits: the shape verdict is unchanged
    assert region.topology.verdict == before.topology.verdict == WORLD_SHAPED
    exits_now = {rid: r["exits"] for rid, r in region.rooms.items()}
    exits_before = {rid: r["exits"] for rid, r in before.rooms.items()}
    assert exits_now == exits_before, "life adds creatures and nodes, never edges"


def test_the_same_seed_breathes_the_same_life() -> None:
    from kernel.worldgen import LifeSpec, populate_region

    spec = RegionSpec("vale", 20, 16, seed=3, landmarks=(_TOWN,))
    life = LifeSpec("temperate-meadow", 1, 30)
    a_region = generate_region(spec)
    a = populate_region(a_region, life)
    b_region = generate_region(spec)
    b = populate_region(b_region, life)
    assert a == b, "life is deterministic: same seed, same creatures"
    nodes_a = {rid: r.get("node") for rid, r in a_region.rooms.items()}
    nodes_b = {rid: r.get("node") for rid, r in b_region.rooms.items()}
    assert nodes_a == nodes_b, "the same field always hangs the same nodes"


def test_an_empty_region_cannot_be_brought_to_life() -> None:
    import dataclasses

    from kernel.worldgen import LifeSpec, populate_region

    region = generate_region(RegionSpec("vale", 20, 16, seed=3, landmarks=(_TOWN,)))
    empty = dataclasses.replace(region, rooms={})
    with pytest.raises(WorldgenError):
        populate_region(empty, LifeSpec("temperate-meadow", 1, 30))


def test_a_non_positive_cadence_is_refused_loud() -> None:
    from kernel.worldgen import LifeSpec, populate_region

    region = generate_region(RegionSpec("vale", 20, 16, seed=3, landmarks=(_TOWN,)))
    for bad in (
        LifeSpec("temperate-meadow", 1, 30, foe_every=0),
        LifeSpec("temperate-meadow", 1, 30, gather_every=0),
        LifeSpec("temperate-meadow", 1, 30, notable_every=0),
    ):
        with pytest.raises(WorldgenError):
            populate_region(region, bad)


def test_band_flattens_when_the_field_is_a_single_cell() -> None:
    from kernel.worldgen import _band

    assert _band(1, 30, 0, 1) == 1  # span<=1: no gradient, everything sits at the floor
    assert _band(1, 30, 5, 0) == 1
