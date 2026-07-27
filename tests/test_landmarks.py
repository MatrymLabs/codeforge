"""Test twin for parts/world/landmarks.py -- a readable monument in every zone's hub.

Acceptance: each zone raises one readable, unequippable monument in its hub (first room), its words
naming the region and the level band, and any dungeon within. Refusal: a hubless zone raises none.
Determinism: the same zone always raises the same monument.
"""

from __future__ import annotations

from parts.world.landmarks import (
    LANDMARK_PREFIX,
    is_landmark,
    raise_landmark,
    raise_landmarks,
)

_ZONES = [
    {
        "name": "Duskwood Vale",
        "region": "Duskwood Vale",
        "rooms": ["duskwood_vale", "ravenwatch", "the_black_hollow"],
        "level_min": 20,
        "level_max": 50,
    },
    {"name": "Veridia", "region": "Veridia", "rooms": ["veridia"], "level_min": 1, "level_max": 30},
]
_DUNGEONS = [{"room": "the_black_hollow", "name": "The Black Hollow", "level": 50}]


def test_a_monument_stands_readable_in_the_zone_hub():
    made = raise_landmark(_ZONES[0], _DUNGEONS)
    assert made is not None
    label, item = made
    assert is_landmark(label) and label == f"{LANDMARK_PREFIX}duskwood_vale"
    assert item["location"] == "room:duskwood_vale", "the monument stands in the zone's first room"
    assert item["slot"] == "" and not item["mods"], "a standing stone is read, not worn"
    assert "monument" in item["keywords"], "`read monument` must resolve it"


def test_the_words_name_the_region_the_band_and_the_dungeon():
    _, item = raise_landmark(_ZONES[0], _DUNGEONS)
    lore = item["lore"]
    assert "Duskwood Vale" in lore and "level 20 to 50" in lore
    assert "The Black Hollow" in lore, "a zone with a dungeon warns of it"


def test_a_zone_without_a_dungeon_raises_a_monument_but_no_warning():
    _, item = raise_landmark(_ZONES[1], _DUNGEONS)
    assert "Veridia" in item["lore"]
    assert "Beware" not in item["lore"], "no dungeon in the zone, no warning"


def test_one_monument_per_zone_hub():
    raised = raise_landmarks(_ZONES, _DUNGEONS)
    assert set(raised) == {f"{LANDMARK_PREFIX}duskwood_vale", f"{LANDMARK_PREFIX}veridia"}


def test_a_hubless_zone_is_skipped_and_forging_is_deterministic():
    assert raise_landmark({"name": "Void", "rooms": []}, _DUNGEONS) is None
    assert raise_landmark(_ZONES[0], _DUNGEONS) == raise_landmark(_ZONES[0], _DUNGEONS)
