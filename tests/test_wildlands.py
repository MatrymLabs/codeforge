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


def test_regions_can_chain_off_earlier_generated_rooms():
    """A region may attach to a room an EARLIER region generated (so a few anchors grow a sprawl).
    The chained region is fully reachable and its attach exit is reciprocal with the trail-head."""
    a = dict(_CFG, id="wa", attach="anchor", attach_dir="east", trail_length=10)
    b = dict(_CFG, id="wb", attach="wa_t5", attach_dir="north", trail_length=10)
    rooms, npcs = generate_wildlands([a, b], {"anchor"})
    world = {"anchor": {"name": "A", "desc": "d", "exits": {}}}
    world.update(rooms)
    wire_attach_exits(world, [a, b])
    # every room reachable from the anchor, including the chained region
    seen, q = {"anchor"}, deque(["anchor"])
    while q:
        for dest in world[q.popleft()]["exits"].values():
            if dest not in seen:
                seen.add(dest)
                q.append(dest)
    assert "wb_t1" in seen and "wb_t10" in seen, "the chained region is unreachable"
    # the chain's attach exit and the trail-head's back exit are reciprocal
    head_back = [d for d, dst in rooms["wb_t1"]["exits"].items() if dst == "wa_t5"]
    assert head_back, "chained trail-head has no exit back to its attach room"


# --- named guardians: MMO-density hunt content seeded by the generator -------------------------


def test_notable_guardians_seed_nonambient_bounty_targets_when_configured():
    cfg = dict(_CFG, id="guard_wild", trail_length=60, notable_every=20)
    _, rooms, npcs = _world_with(cfg)
    lords = {k: v for k, v in npcs.items() if "_lord_" in k}
    assert lords, "a configured region seeded no named guardian"
    for v in lords.values():
        assert not v.get("ambient"), (
            "a guardian must be non-ambient (so register_bounties names it)"
        )
        assert v["hp"] > 0 and v["tier"] in ("elite", "boss")
        assert v["location"] in rooms  # it stands in a generated room
    # a guardian REPLACES its room's ambient life, so there is still exactly one creature per room
    occupied = [npc["location"] for npc in npcs.values()]
    assert len(occupied) == len(set(occupied)) == len(rooms)


def test_notables_are_off_by_default_in_a_hand_built_config():
    _, _, npcs = _world_with(_CFG)  # _CFG declares no notable_every
    assert not any("_lord_" in k for k in npcs), "a quiet config seeded a guardian anyway"


def test_the_guardian_count_is_capped_for_a_huge_region():
    from parts.world.wildlands import _NOTABLE_CAP

    cfg = dict(_CFG, id="huge_wild", trail_length=_NOTABLE_CAP * 40, notable_every=1)
    _, _, npcs = _world_with(cfg)
    assert len([k for k in npcs if "_lord_" in k]) == _NOTABLE_CAP  # bounded, however large


def test_notable_every_defaults_on_and_refuses_a_negative():
    import tempfile
    from pathlib import Path

    import yaml

    from parts.world.wildlands import load_wildlands_config

    good = {k: v for k, v in _CFG.items() if k != "id"}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "wildlands.yaml"
        p.write_text(yaml.safe_dump({"probe_wild": good}))
        cfg = load_wildlands_config(p)[0]
        assert cfg["notable_every"] > 0  # the loader turns hunt content on by default
        p.write_text(yaml.safe_dump({"probe_wild": {**good, "notable_every": -1}}))
        with pytest.raises(SeedError, match="notable_every"):
            load_wildlands_config(p)


# --- CODEFORGE_WILD_SCALE: one seed, demo-to-MMO scale by env -----------------------------------


def _write_cfg(tmp_path):
    import yaml

    p = tmp_path / "wildlands.yaml"
    p.write_text(yaml.safe_dump({"probe_wild": {k: v for k, v in _CFG.items() if k != "id"}}))
    return p


def test_wild_scale_multiplies_every_region_trail(monkeypatch, tmp_path):
    from parts.world.wildlands import load_wildlands_config

    p = _write_cfg(tmp_path)
    monkeypatch.delenv("CODEFORGE_WILD_SCALE", raising=False)
    base = load_wildlands_config(p)[0]["trail_length"]
    assert base == _CFG["trail_length"]  # default = the seed's shipped size
    monkeypatch.setenv("CODEFORGE_WILD_SCALE", "10")
    assert load_wildlands_config(p)[0]["trail_length"] == base * 10  # env grows the world


@pytest.mark.parametrize("bad", ["abc", "0", "0.5", "-3"])
def test_wild_scale_refuses_a_bad_or_shrinking_value(monkeypatch, tmp_path, bad):
    from parts.world.wildlands import load_wildlands_config

    p = _write_cfg(tmp_path)
    monkeypatch.setenv("CODEFORGE_WILD_SCALE", bad)
    with pytest.raises(SeedError, match="CODEFORGE_WILD_SCALE"):
        load_wildlands_config(p)
