"""Test twin for kernel/world/rumors.py -- town gossip that points at real nearby content.

Acceptance: a resident of a dungeon-bearing zone gains a `rumor` topic (and a woven greeting) naming
that zone's dungeon and the relic it guards. Refusal: a town in a dungeonless zone is left silent;
merchants keep to their wares. Determinism: the relic named is the one relics.forge_relic makes.
"""

from __future__ import annotations

from kernel.world.relics import forge_relic
from kernel.world.rumors import seed_rumors
from kernel.world.seed import Npc

_ZONES = [
    {"name": "Duskwood Vale", "rooms": ["ravenwatch", "the_black_hollow"], "level_max": 50},
    {"name": "Veridia", "rooms": ["greenhold"], "level_max": 30},  # a dungeonless zone
]
_DUNGEONS = [{"room": "the_black_hollow", "name": "The Black Hollow", "level": 50}]


def _folk(room: str, shop: bool = False) -> Npc:
    npc = Npc(
        name="a smith",
        keywords=["smith"],
        location=room,
        dialogue=['The smith nods. "Fair day."'],
        next_line=0,
        hp=0,
        hp_now=0,
        xp=0,
        atk=0,
        topics={"town": ["A good place to rest."]},
    )
    if shop:
        npc["shop"] = {"sells": {}, "buys": {}}
    return npc


def test_a_resident_of_a_dungeon_zone_gains_a_rumor_naming_the_dungeon_and_relic():
    folk = {"ravenwatch_dweller_0": _folk("ravenwatch")}
    touched = seed_rumors(folk, _ZONES, _DUNGEONS)
    assert touched == 1
    rumor = folk["ravenwatch_dweller_0"]["topics"]["rumor"][0]
    _, relic = forge_relic("the_black_hollow", "The Black Hollow", 50, 0)
    assert "The Black Hollow" in rumor, "the gossip names the real dungeon"
    assert relic["name"] in rumor, "and the very relic relics.forge_relic makes"


def test_the_rumor_is_woven_into_the_greeting_too():
    folk = {"ravenwatch_dweller_0": _folk("ravenwatch")}
    seed_rumors(folk, _ZONES, _DUNGEONS)
    dialogue = folk["ravenwatch_dweller_0"]["dialogue"]
    assert len(dialogue) == 2, "the rumour is appended, the original greeting kept"
    assert "The Black Hollow" in dialogue[-1]


def test_a_town_in_a_dungeonless_zone_stays_silent():
    folk = {"greenhold_dweller_0": _folk("greenhold")}
    assert seed_rumors(folk, _ZONES, _DUNGEONS) == 0
    assert "rumor" not in folk["greenhold_dweller_0"]["topics"]


def test_a_merchant_keeps_to_its_wares():
    folk = {"ravenwatch_merchant": _folk("ravenwatch", shop=True)}
    assert seed_rumors(folk, _ZONES, _DUNGEONS) == 0
    assert "rumor" not in folk["ravenwatch_merchant"]["topics"]


def test_rumor_lines_vary_across_a_crowd():
    folk = {f"ravenwatch_dweller_{i}": _folk("ravenwatch") for i in range(4)}
    seed_rumors(folk, _ZONES, _DUNGEONS)
    lines = {npc["topics"]["rumor"][0] for npc in folk.values()}
    assert len(lines) > 1, "a plaza should not tell the identical rumour four times"
