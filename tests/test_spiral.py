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


def test_generation_is_deterministic():
    a = generate_spiral(_CONFIG, _ROOMS)
    b = generate_spiral(_CONFIG, _ROOMS)
    assert a == b  # no randomness: the world is reproducible


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


def test_the_flagship_seed_reaches_the_summit_at_the_level_cap():
    from parts.shelf.reward_curve import LEVEL_MAX
    from parts.world.seed import SEEDS_ROOT

    config = load_spiral_config(SEEDS_ROOT / "aethryn" / "spiral.yaml")
    assert config is not None and config["top_level"] == 300 == LEVEL_MAX  # the true ceiling
    _rooms, npcs, first = generate_spiral(config, {"coil_third_landing": {"exits": {}}})
    assert any(n["level"] == 300 for n in npcs.values())  # the aethryn Road runs to the cap
    assert first == "coil_4_ascent"
    # no dead band at the hand-authored/procedural seam: the lowest generated foe lands right above
    # the last authored foe (the Stormlord, level 38), so the road never runs out of content.
    lowest = min(n["level"] for n in npcs.values())
    assert 38 < lowest <= 40, f"a dead band opened at the Spiral seam (lowest generated {lowest})"


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
