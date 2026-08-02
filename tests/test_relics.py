"""Test twin for kernel/world/relics.py -- signature legendary boss drops.

Acceptance: every dungeon's deep boss gains one named, legendary, readable relic as a GUARANTEED
drop, on top of whatever generic gear it already carries, deterministically. Refusal: a dungeon
whose deep boss is absent is skipped; no boss loses a drop it already had.
"""

from __future__ import annotations

from kernel.world.relics import (
    DEEP_BOSS_SUFFIX,
    RELIC_PREFIX,
    arm_deep_bosses,
    forge_relic,
    is_relic,
)
from kernel.world.seed import Npc

_DUNGEONS = [
    {"room": "the_black_hollow", "name": "The Black Hollow", "level": 50},
    {"room": "glacial_bastion", "name": "Glacial Bastion", "level": 90},
]


def _boss(level: int, drops: list[str] | None = None) -> Npc:
    npc = Npc(
        name="deep terror",
        keywords=["terror"],
        location="nowhere",
        dialogue=[],
        next_line=0,
        hp=500,
        hp_now=500,
        xp=0,
        atk=10,
        level=level,
        tier="boss",
    )
    if drops is not None:
        npc["drops"] = drops
    return npc


def test_forged_relic_is_named_legendary_and_readable():
    label, item = forge_relic("the_black_hollow", "The Black Hollow", 50, 0)
    assert is_relic(label) and label == f"{RELIC_PREFIX}the_black_hollow"
    assert item["rarity"] == "legendary"
    assert "Black" in item["name"], "the relic borrows its dungeon's iconic word"
    assert "The Black Hollow" in item["lore"], "the lore names the terror it was torn from"
    assert item["slot"] and item["mods"], "a relic is a real equippable"


def test_relic_stats_scale_with_level():
    _, low = forge_relic("a_pit", "A Pit", 20, 0)
    _, high = forge_relic("a_pit", "A Pit", 200, 0)
    assert max(high["mods"].values()) > max(low["mods"].values())


def test_every_deep_boss_gains_its_signature_relic_as_a_guaranteed_drop():
    npcs = {
        f"the_black_hollow{DEEP_BOSS_SUFFIX}": _boss(50, drops=["gear_shadow_cleaver_l50"]),
        f"glacial_bastion{DEEP_BOSS_SUFFIX}": _boss(90),
    }
    relics = arm_deep_bosses(_DUNGEONS, npcs)
    assert len(relics) == 2, "one relic prototype per dungeon"
    hollow = npcs[f"the_black_hollow{DEEP_BOSS_SUFFIX}"]["drops"]
    assert "gear_shadow_cleaver_l50" in hollow, (
        "the relic ADDS to the generic drop, never replaces it"
    )
    assert f"{RELIC_PREFIX}the_black_hollow" in hollow


def test_a_dungeon_without_a_deep_boss_is_skipped():
    relics = arm_deep_bosses(_DUNGEONS, {})  # no boss npcs present
    assert relics == {}


def test_arming_is_idempotent():
    npcs = {f"glacial_bastion{DEEP_BOSS_SUFFIX}": _boss(90)}
    arm_deep_bosses(_DUNGEONS, npcs)
    arm_deep_bosses(_DUNGEONS, npcs)  # a second pass must not double-add the relic
    drops = npcs[f"glacial_bastion{DEEP_BOSS_SUFFIX}"]["drops"]
    assert drops.count(f"{RELIC_PREFIX}glacial_bastion") == 1
