"""Test twin for parts/world/spine.py -- the world's main-road campaign quest.

Acceptance: the spine chains the zones in level order, one beat per arrival, from the starting band
to the endgame, with a reward on the final leg. Refusal: a world with fewer than two zones lays no
road. Determinism: the same zones always lay the same road.
"""

from __future__ import annotations

from parts.world.spine import SPINE_ID, forge_spine, is_spine

_ZONES = [
    {
        "name": "Zhaar Desert",
        "rooms": ["zhaar_desert", "red_dunes"],
        "level_min": 80,
        "level_max": 130,
    },
    {"name": "Veridia", "rooms": ["veridia", "greenhold"], "level_min": 1, "level_max": 30},
    {"name": "Caeloria", "rooms": ["caeloria", "brightwater"], "level_min": 30, "level_max": 60},
]


def test_the_road_chains_zones_in_level_order():
    spine = forge_spine(_ZONES)
    assert spine is not None
    assert is_spine(spine["id"]) and spine["id"] == SPINE_ID
    # three zones -> two legs (arrivals at zone 2 and zone 3)
    hubs = [step["on_enter"] for step in spine["steps"]]
    assert hubs == ["caeloria", "zhaar_desert"], "beats arrive at each next zone's hub, in order"


def test_the_start_names_the_first_and_last_zone():
    spine = forge_spine(_ZONES)
    assert spine is not None
    start = spine["labels"][spine["start"]]
    assert "Veridia" in start and "Zhaar Desert" in start, (
        "the road spans the starting band to endgame"
    )


def test_the_reward_lands_on_the_final_leg_and_scales_with_the_top_cap():
    spine = forge_spine(_ZONES)
    assert spine is not None
    assert spine["steps"][-1].get("effect") == "award_xp", "the payoff is reaching the last zone"
    assert spine["steps"][0].get("effect") is None, "no reward for the early legs"
    assert spine["reward_xp"] == 130 * 40, "the campaign scales with the endgame zone's level cap"


def test_a_world_with_fewer_than_two_zones_lays_no_road():
    assert forge_spine([]) is None
    assert forge_spine([_ZONES[0]]) is None


def test_the_road_is_deterministic():
    assert forge_spine(_ZONES) == forge_spine(list(reversed(_ZONES)))
