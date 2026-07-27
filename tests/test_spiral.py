"""Test twin for parts.world.spiral: the procedural Forgeward Road generator.

Acceptance (a valid config generates a road east to the far end at the level cap) AND refusal
(a malformed config, an attach room that does not exist) plus determinism (same config -> same
world). The generator emits seed-shaped Room/Npc data, so the assertions check that shape.
"""

import pytest

from parts.world.seed import SeedError
from parts.world.spiral import generate_spiral, load_spiral_config

_CONFIG = {
    "attach": "base",
    "first_coil": 4,
    "base_level": 47,
    "levels_per_coil": 9,
    "top_level": 255,
}
_ROOMS = {"base": {"name": "Base", "desc": "", "exits": {"west": "below"}}}


def test_generation_chains_marches_from_attach_east_to_the_far_end():
    rooms, npcs, first = generate_spiral(_CONFIG, _ROOMS)
    assert first == "coil_4_ascent"
    # the attach room's east should point at the first march (the caller wires it; we report it)
    assert rooms["coil_4_ascent"]["exits"]["west"] == "base"
    assert rooms["coil_4_ascent"]["exits"]["east"] == "coil_4_landing"
    # every generated exit resolves within the generated set (plus the attach room)
    known = set(rooms) | set(_ROOMS)
    for room in rooms.values():
        for dest in room["exits"].values():
            assert dest in known, f"dangling exit -> {dest}"


def test_the_summit_boss_stands_at_the_level_cap():
    rooms, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    bosses = [n for n in npcs.values() if n.get("tier") == "boss"]
    top = max(b["level"] for b in bosses)
    assert top == 255  # the far road-warden reaches the configured cap
    summit_boss = next(b for b in bosses if b["level"] == 255)
    assert summit_boss.get("lethal") is True and summit_boss["name"] == "the Sovereign"
    # the far room is a dead-end (no `east`), every march before it runs on outward
    summit_landing = next(r for r in rooms.values() if r["name"] == "The Forge's Edge")
    assert "east" not in summit_landing["exits"]


def test_each_coils_gate_boss_climbs_above_the_last():
    _, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    levels = sorted(n["level"] for n in npcs.values() if n.get("tier") == "boss")
    assert levels == sorted(set(levels))  # strictly increasing, no duplicate wall
    assert levels[0] == 47 and levels[-1] == 255


def test_extend_world_with_road_merges_and_wires_the_attach_exit():
    """The world-wiring helper (what world.py calls) merges the generated marches into a seed's
    world and grows the attach room's flat `east` exit onto the first march -- no climb, no `up`."""
    from parts.world.spiral import extend_world_with_road

    world = {"base": {"name": "Base", "desc": "", "exits": {"west": "below"}}}
    npcs: dict = {}
    first = extend_world_with_road(world, npcs, _CONFIG)
    assert first == "coil_4_ascent"
    assert world["base"]["exits"]["east"] == "coil_4_ascent"  # attach room wired east, not up
    assert "coil_4_ascent" in world  # the generated rooms merged in
    assert any(n.get("tier") == "boss" for n in npcs.values())  # and the road-wardens merged in
    assert "up" not in world["base"]["exits"]  # the flat world never climbs


def test_generation_is_deterministic():
    a = generate_spiral(_CONFIG, _ROOMS)
    b = generate_spiral(_CONFIG, _ROOMS)
    assert a == b  # no randomness: the world is reproducible


def test_the_frontier_forks_to_exploration_waysides():
    """The flat frontier is a wide land, not a single corridor: some marches fork off the road to a
    WAYSIDE, a dead-end side-track with a themed hoard-guardian over loot. It is optional (a normal
    foe, not a lethal gate), and only SOME marches have one (a rhythm, not one on every stretch)."""
    rooms, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    # march 4 (the first) forks to a wayside; march 5 does not (every-other rhythm)
    assert "coil_4_wayside" in rooms and "coil_5_wayside" not in rooms
    # the road room grows a side exit onto the wayside, and the wayside dead-ends back to the march
    ascent = rooms["coil_4_ascent"]["exits"]
    branch = next(d for d, dest in ascent.items() if dest == "coil_4_wayside")
    assert branch in ("north", "south")  # a side-track off the east/west road
    back = rooms["coil_4_wayside"]["exits"]
    assert list(back.values()) == ["coil_4_ascent"]  # a dead-end back to the road, no dangling exit
    # the guardian is a NORMAL foe (not a road-warden boss) but still carries loot to reward the
    # detour, and it out-levels the march's husk (a real optional fight, not a farm mob)
    guard = npcs["spiral_wayside_4"]
    assert guard["tier"] == "normal" and "lethal" not in guard
    assert guard["attack_element"] == "FIR"
    assert guard["level"] > npcs["spiral_husk_4"]["level"]
    # exploration pays DIFFERENT loot from the road: wardens drop weapons, a wayside drops the
    # keystone ACCESSORY -- so a mid-road Forger can earn one instead of it gating behind the cap
    assert guard["drops"] == ["coil_keystone"]
    assert npcs["spiral_gate_4"]["drops"] == ["ember_brand"]  # the road-warden still drops a weapon


def test_each_coil_takes_a_rotating_elemental_theme():
    """The frontier is a varied gauntlet, not one room 50 times: consecutive marches carry different
    elements, and a road-warden is an elemental puzzle (resists its element, weak to a counter)."""
    _, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    w4, w5 = npcs["spiral_gate_4"], npcs["spiral_gate_5"]
    assert w4["attack_element"] == "FIR" and w5["attack_element"] == "ICE"  # varies march to march
    assert w4["resistances"] == {"FIR": "Resist", "ICE": "Weak"}  # bring frost to a fire march
    # each themed warden drops its own themed weapon (varied endgame loot, not one keystone x25);
    # combat's affix factory then rolls a rarity onto the levelled drop
    assert w4["drops"] == ["ember_brand"] and w5["drops"] == ["rime_edge"]
    # a husk carries the element (typed blows) but no grid, so it stays farmable with any move
    husk = npcs["spiral_husk_4"]
    assert husk["attack_element"] == "FIR" and "resistances" not in husk


def test_the_summit_sovereign_stays_an_untyped_final_test():
    from parts.world.spiral import SUMMIT_BOSS

    _, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    sovereign = npcs[SUMMIT_BOSS]
    assert "attack_element" not in sovereign and "resistances" not in sovereign


def test_the_summit_boss_drops_the_configured_legendary_or_a_default():
    """The final boss deserves a capstone: a seed may name a legendary via `summit_drop`, and the
    Sovereign drops it. With no `summit_drop`, it falls back to the road keystone (not nothing)."""
    from parts.world.spiral import SUMMIT_BOSS

    _, npcs, _ = generate_spiral(_CONFIG, _ROOMS)  # _CONFIG ships no summit_drop
    assert npcs[SUMMIT_BOSS]["drops"] == ["coil_keystone"]  # the honest default
    _, npcs2, _ = generate_spiral({**_CONFIG, "summit_drop": "a_legendary"}, _ROOMS)
    assert npcs2[SUMMIT_BOSS]["drops"] == ["a_legendary"]  # the seed's named capstone


def test_load_spiral_config_rejects_a_non_string_summit_drop(tmp_path):
    path = tmp_path / "spiral.yaml"
    path.write_text(
        "attach: a\nfirst_coil: 4\nbase_level: 47\nlevels_per_coil: 9\ntop_level: 255\n"
        "summit_drop: 7\n"  # a number, not an item label
    )
    with pytest.raises(SeedError, match="summit_drop"):
        load_spiral_config(path)


def test_an_attach_room_that_does_not_exist_is_refused():
    with pytest.raises(SeedError, match="attach"):
        generate_spiral({**_CONFIG, "attach": "nowhere_real"}, _ROOMS)


def test_load_spiral_config_returns_none_when_absent(tmp_path):
    assert load_spiral_config(tmp_path / "spiral.yaml") is None  # a seed with no extension


def test_load_spiral_config_rejects_a_missing_key(tmp_path):
    path = tmp_path / "spiral.yaml"
    path.write_text("attach: coil_third_landing\nfirst_coil: 4\n")  # missing level fields
    with pytest.raises(SeedError, match="missing required key"):
        load_spiral_config(path)


def test_load_spiral_config_rejects_a_top_above_the_curve_cap(tmp_path):
    path = tmp_path / "spiral.yaml"
    path.write_text(
        "attach: a\nfirst_coil: 4\nbase_level: 47\nlevels_per_coil: 9\ntop_level: 9999\n"
    )
    with pytest.raises(SeedError, match="top_level"):
        load_spiral_config(path)


def test_spiral_zones_name_every_generated_coil():
    """The generated marches get area identity: every generated room lands in exactly one named zone
    (so the frontier renders an '[Area: The Nth March]' banner, not an anonymous stretch)."""
    from parts.world.spiral import SUMMIT_ROOM, spiral_zones

    rooms, _, _ = generate_spiral(_CONFIG, _ROOMS)
    zones = spiral_zones(_CONFIG)
    zoned = [room for zone in zones.values() for room in zone["rooms"]]
    assert set(zoned) == set(rooms)  # exact cover: no generated room is left anonymous
    assert len(zoned) == len(set(zoned))  # and none is in two zones
    summit_zone = next(z for z in zones.values() if SUMMIT_ROOM in z["rooms"])
    assert summit_zone["name"] == "The Forge's Edge"  # the far end is its own named area


def test_the_summit_uses_stable_labels_for_a_capstone_quest():
    """The far room + road-warden carry fixed labels (not the march number), so a quest can name
    them however far the Road runs."""
    from parts.world.spiral import SUMMIT_BOSS, SUMMIT_ROOM

    rooms, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    assert SUMMIT_ROOM in rooms and SUMMIT_ROOM == "the_spiral_summit"
    assert SUMMIT_BOSS in npcs and npcs[SUMMIT_BOSS]["level"] == 255
    assert npcs[SUMMIT_BOSS]["location"] == SUMMIT_ROOM
