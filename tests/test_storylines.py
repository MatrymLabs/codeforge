"""Test twin for kernel/world/storylines.py -- generated zone narrative chains.

Acceptance: a zone that pairs a town with a dungeon gets one three-beat tale (reach the dungeon ->
slay its deep boss -> bear word home), keyed and rewarded off the world's own geography. Refusal: a
zone missing a town OR a dungeon gets no tale; empty inputs yield nothing. Integration: the arc is
well-formed and its triggers target the real destination rooms and the delve's deep-boss npc key.
"""

from __future__ import annotations

from kernel.world.storylines import (
    DEEP_BOSS_SUFFIX,
    STORY_PREFIX,
    generate_storylines,
    is_storyline,
)

_ZONES = [
    # a full zone: has both a town and a dungeon among its rooms
    {
        "name": "Duskwood Vale",
        "region": "Duskwood Vale",
        "rooms": ["ravenwatch", "the_black_hollow"],
        "level_max": 50,
    },
    # a townless zone: only a dungeon -> no tale
    {"name": "Wildlands", "region": "The Wilds", "rooms": ["glacial_bastion"], "level_max": 90},
    # a dungeonless zone: only a town -> no tale
    {"name": "Veridia", "region": "Veridia", "rooms": ["greenhold", "sunmeadow"], "level_max": 30},
]
_SETTLEMENTS = [
    {"room": "ravenwatch", "name": "Ravenwatch", "level": 25},
    {"room": "greenhold", "name": "Greenhold", "level": 1},
]
_DUNGEONS = [
    {"room": "the_black_hollow", "name": "The Black Hollow", "zone": "Duskwood Vale", "level": 50},
    {"room": "glacial_bastion", "name": "Glacial Bastion", "zone": "Wildlands", "level": 90},
]


def test_a_zone_with_a_town_and_a_dungeon_gets_one_three_beat_tale():
    tales = generate_storylines(_ZONES, _SETTLEMENTS, _DUNGEONS)
    assert len(tales) == 1, "only the town+dungeon zone should carry a tale"
    tale = tales[0]
    assert is_storyline(tale["id"]) and tale["id"] == f"{STORY_PREFIX}ravenwatch"
    assert len(tale["steps"]) == 3, "reach -> slay -> deliver"


def test_the_three_beats_target_the_real_geography_and_the_deep_boss():
    tale = generate_storylines(_ZONES, _SETTLEMENTS, _DUNGEONS)[0]
    reach, slay, deliver = tale["steps"]
    assert reach["on_enter"] == "the_black_hollow", "beat 1 sends the player into the dungeon"
    assert slay["on_defeat"] == f"the_black_hollow{DEEP_BOSS_SUFFIX}", (
        "beat 2 fells the delve's deep boss"
    )
    assert deliver["on_enter"] == "ravenwatch", "beat 3 bears word home to the town"
    assert deliver["effect"] == "award_xp", "the reward lands on delivery, not before"


def test_the_reward_scales_with_the_zones_level_cap():
    tale = generate_storylines(_ZONES, _SETTLEMENTS, _DUNGEONS)[0]
    assert tale["reward_xp"] == 50 * 25, "a level-50 capstone pays 25 XP per cap level"


def test_a_zone_missing_a_town_or_a_dungeon_gets_no_tale():
    dungeon_only = [{"name": "z", "region": "r", "rooms": ["glacial_bastion"], "level_max": 90}]
    town_only = [{"name": "z", "region": "r", "rooms": ["greenhold"], "level_max": 30}]
    assert generate_storylines(dungeon_only, _SETTLEMENTS, _DUNGEONS) == []
    assert generate_storylines(town_only, _SETTLEMENTS, _DUNGEONS) == []


def test_empty_inputs_yield_no_tales():
    assert generate_storylines([], _SETTLEMENTS, _DUNGEONS) == []
    assert generate_storylines(_ZONES, [], _DUNGEONS) == []
    assert generate_storylines(_ZONES, _SETTLEMENTS, []) == []


def test_the_hook_advertises_before_the_player_touches_it():
    # the chain starts 'afoot' so contracts_view can render its hook without the player acting yet.
    tale = generate_storylines(_ZONES, _SETTLEMENTS, _DUNGEONS)[0]
    assert tale["start"] == "afoot"
    assert "The Black Hollow" in tale["labels"]["afoot"] and "Ravenwatch" in tale["labels"]["afoot"]
