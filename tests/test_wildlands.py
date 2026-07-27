"""Test twin for parts/world/wildlands.py -- the deterministic wilderness generator.

Acceptance: a config expands into a connected, fully-reachable region of rooms, each with ambient
life and a metadata area. Refusal: a malformed config fails loud. Regression: branches never
overwrite the trail spine (the orphan bug), and the expansion is reproducible.
"""

from collections import deque

import pytest

from parts.world.seed import SeedError
from parts.world.wildlands import (
    generate_wildlands,
    wildlands_zones,
    wire_attach_exits,
)

_CFG = {
    "id": "probe_wild",
    "name": "The Probe Wilds",
    "region": "Emberreach",
    "biome": "temperate-meadow",
    "attach": "anchor",
    "attach_dir": "east",
    "level_min": 4,
    "level_max": 12,
    "trail_length": 20,
    "branch_every": 3,
    "branch_length": 3,
}


def _world_with(cfg):
    rooms, npcs = generate_wildlands([cfg], {"anchor"})
    world = {"anchor": {"name": "Anchor", "desc": "the attach room", "exits": {}}}
    world.update(rooms)
    wire_attach_exits(world, [cfg])
    return world, rooms, npcs


def test_region_expands_and_is_fully_reachable_from_the_attach_room():
    world, rooms, npcs = _world_with(_CFG)
    # BFS from the attach room reaches every generated room -- no orphans, no dead clouds.
    seen, q = {"anchor"}, deque(["anchor"])
    while q:
        for dest in world[q.popleft()]["exits"].values():
            if dest not in seen:
                seen.add(dest)
                q.append(dest)
    assert set(rooms).issubset(seen), "a generated room is unreachable from the attach point"


def test_every_generated_room_carries_ambient_life():
    _, rooms, npcs = _world_with(_CFG)
    occupied = {npc["location"] for npc in npcs.values()}
    assert set(rooms) == occupied, "a generated room shipped with no ambient creature"


def test_every_exit_resolves_within_the_world():
    world, rooms, _ = _world_with(_CFG)
    for label, room in rooms.items():
        for direction, dest in room["exits"].items():
            assert dest in world, f"{label} exit {direction} -> {dest} dangles"


def test_branches_never_overwrite_the_trail_spine():
    # Regression: with the trail running `east`, a branch must not also leave `east` (it would
    # overwrite the spine and orphan the rooms ahead). Every trail room keeps its forward link.
    _, rooms, _ = _world_with(_CFG)
    L = _CFG["trail_length"]
    for i in range(1, L):  # t1..t(L-1) must each keep an east link to the next trail room
        room = rooms[f"probe_wild_t{i}"]
        assert room["exits"].get("east") == f"probe_wild_t{i + 1}", f"t{i} lost its spine"


def test_generation_is_deterministic():
    a, _ = generate_wildlands([_CFG], {"anchor"})
    b, _ = generate_wildlands([_CFG], {"anchor"})
    assert {k: v["desc"] for k, v in a.items()} == {k: v["desc"] for k, v in b.items()}


def test_zone_covers_every_generated_room_with_metadata():
    _, rooms, _ = _world_with(_CFG)
    zones = wildlands_zones([_CFG])
    zoned = {r for z in zones.values() for r in z["rooms"]}
    assert set(rooms) == zoned, "a generated room is left out of its metadata area"
    z = zones["wildlands_probe_wild"]
    assert z["region"] == "Emberreach" and z["level_min"] == 4 and z["biome"] == "temperate-meadow"


def test_attach_room_gains_exactly_one_exit_into_the_region():
    world, _, _ = _world_with(_CFG)
    assert world["anchor"]["exits"].get("east") == "probe_wild_t1"


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"biome": "moon-cheese"}, "biome"),
        ({"attach_dir": "sideways"}, "attach_dir"),
        ({"level_min": 50, "level_max": 20}, "level_min <= level_max"),
        ({"trail_length": 0}, "trail_length"),
    ],
)
def test_a_malformed_region_fails_loud(bad, match):
    from parts.world.wildlands import load_wildlands_config

    cfg = {k: v for k, v in _CFG.items() if k != "id"}
    cfg.update(bad)
    tmp = {"probe_wild": cfg}
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        import yaml

        p = Path(d) / "wildlands.yaml"
        p.write_text(yaml.safe_dump(tmp))
        with pytest.raises(SeedError, match=match):
            load_wildlands_config(p)


def test_a_config_attaching_to_a_missing_room_is_refused():
    with pytest.raises(SeedError, match="not a real room"):
        generate_wildlands([_CFG], set())  # 'anchor' does not exist
