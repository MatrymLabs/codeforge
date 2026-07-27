"""Test twin for parts/world/inscriptions.py -- readable lore carved into dungeon boss chambers.

Acceptance: each dungeon gets one readable, unequippable inscription lying in its boss chamber, its
words naming the dungeon and the very relic relics.forge_relic makes. Determinism: same dungeon,
same words. Integration: the words vary across dungeons; the item reads via the `lore` field.
"""

from __future__ import annotations

from parts.world.delve import boss_chamber
from parts.world.inscriptions import (
    INSCRIPTION_PREFIX,
    carve_inscription,
    carve_inscriptions,
    is_inscription,
)
from parts.world.relics import forge_relic

_DUNGEONS = [
    {"room": "the_black_hollow", "name": "The Black Hollow", "level": 50},
    {"room": "glacial_bastion", "name": "Glacial Bastion", "level": 90},
]


def test_an_inscription_lies_in_the_boss_chamber_and_is_readable():
    label, item = carve_inscription("the_black_hollow", "The Black Hollow", 50, 0)
    assert is_inscription(label) and label == f"{INSCRIPTION_PREFIX}the_black_hollow"
    assert item["location"] == f"room:{boss_chamber('the_black_hollow')}"
    assert item["slot"] == "" and not item["mods"], "a wall carving is read, not worn"
    assert item["lore"], "there is something written to read"
    assert "inscription" in item["keywords"], "`read inscription` must resolve it"


def test_the_words_name_the_dungeon_and_the_real_relic():
    _, item = carve_inscription("the_black_hollow", "The Black Hollow", 50, 0)
    _, relic = forge_relic("the_black_hollow", "The Black Hollow", 50, 0)
    assert "The Black Hollow" in item["lore"]
    assert relic["name"] in item["lore"], (
        "the inscription confirms the very relic forge_relic makes"
    )


def test_one_inscription_per_dungeon_with_varied_words():
    carved = carve_inscriptions(_DUNGEONS)
    assert len(carved) == len(_DUNGEONS)
    assert all(is_inscription(label) for label in carved)
    words = {item["lore"] for item in carved.values()}
    assert len(words) == len(_DUNGEONS), "each dungeon reads differently"


def test_carving_is_deterministic():
    a = carve_inscription("a_pit", "A Pit", 30, 1)
    b = carve_inscription("a_pit", "A Pit", 30, 1)
    assert a == b


def test_no_dungeons_yields_no_inscriptions():
    assert carve_inscriptions([]) == {}
