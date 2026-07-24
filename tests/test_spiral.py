"""Test twin for parts.world.spiral: the procedural Great Spiral generator.

Acceptance (a valid config generates a chained climb to the summit at the level cap) AND refusal
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
_ROOMS = {"base": {"name": "Base", "desc": "", "exits": {"down": "below"}}}


def test_generation_chains_coils_from_attach_up_to_the_summit():
    rooms, npcs, first = generate_spiral(_CONFIG, _ROOMS)
    assert first == "coil_4_ascent"
    # the attach room's up should point at the first Coil (the caller wires it; we report it)
    assert rooms["coil_4_ascent"]["exits"]["down"] == "base"
    assert rooms["coil_4_ascent"]["exits"]["up"] == "coil_4_landing"
    # every generated exit resolves within the generated set (plus the attach room)
    known = set(rooms) | set(_ROOMS)
    for room in rooms.values():
        for dest in room["exits"].values():
            assert dest in known, f"dangling exit -> {dest}"


def test_the_summit_boss_stands_at_the_level_cap():
    rooms, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    bosses = [n for n in npcs.values() if n.get("tier") == "boss"]
    top = max(b["level"] for b in bosses)
    assert top == 255  # the summit Gate-boss reaches the configured cap
    summit_boss = next(b for b in bosses if b["level"] == 255)
    assert summit_boss.get("lethal") is True and summit_boss["name"] == "the Spiral Sovereign"
    # the summit landing is a dead-end top (no `up`), every Coil below climbs on
    summit_landing = next(r for r in rooms.values() if r["name"] == "The Spiral Summit")
    assert "up" not in summit_landing["exits"]


def test_each_coils_gate_boss_climbs_above_the_last():
    _, npcs, _ = generate_spiral(_CONFIG, _ROOMS)
    levels = sorted(n["level"] for n in npcs.values() if n.get("tier") == "boss")
    assert levels == sorted(set(levels))  # strictly increasing, no duplicate wall
    assert levels[0] == 47 and levels[-1] == 255


def test_generation_is_deterministic():
    a = generate_spiral(_CONFIG, _ROOMS)
    b = generate_spiral(_CONFIG, _ROOMS)
    assert a == b  # no randomness: the world is reproducible


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


def test_the_flagship_seed_reaches_the_summit_at_level_255():
    from parts.world.seed import SEEDS_ROOT

    config = load_spiral_config(SEEDS_ROOT / "aethryn" / "spiral.yaml")
    assert config is not None and config["top_level"] == 255
    _rooms, npcs, first = generate_spiral(config, {"coil_third_landing": {"exits": {}}})
    assert any(n["level"] == 255 for n in npcs.values())  # the aethryn Spiral truly hits 255
    assert first == "coil_4_ascent"
