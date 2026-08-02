"""Test twin for kernel/world/wardens.py -- naming each dungeon's deep boss for its dungeon.

Acceptance: each deep boss is renamed to a titled warden of its dungeon, nameable by title or its
dungeon word, stats untouched. Refusal: a dungeon with no deep boss is skipped. Determinism holds.
"""

from __future__ import annotations

from kernel.world.seed import Npc
from kernel.world.wardens import DEEP_BOSS_SUFFIX, name_wardens

_DUNGEONS = [
    {"room": "the_black_hollow", "name": "The Black Hollow", "level": 50},
    {"room": "glacial_bastion", "name": "Glacial Bastion", "level": 90},
]


def _boss() -> Npc:
    return Npc(
        name="Grathok the Shadow Fiend",
        keywords=["grathok", "fiend"],
        location="the_black_hollow_delve_4",
        dialogue=["Grathok snarls."],
        next_line=0,
        hp=900,
        hp_now=900,
        xp=0,
        atk=40,
        level=55,
        tier="boss",
        lethal=True,
    )


def test_the_boss_is_renamed_for_its_dungeon():
    boss = _boss()
    npcs = {f"the_black_hollow{DEEP_BOSS_SUFFIX}": boss}
    assert name_wardens(_DUNGEONS, npcs) == 1
    assert boss["name"] == "the Warden of The Black Hollow"
    assert "The Black Hollow" in boss["dialogue"][0]


def test_the_warden_answers_to_its_title_and_its_dungeon():
    boss = _boss()
    name_wardens(_DUNGEONS, {f"the_black_hollow{DEEP_BOSS_SUFFIX}": boss})
    assert "warden" in boss["keywords"], "`kill warden` resolves it"
    assert "black" in boss["keywords"], "so does the dungeon's own word"


def test_only_identity_changes_not_the_fight():
    boss = _boss()
    hp, atk, tier, lethal = boss["hp"], boss["atk"], boss["tier"], boss["lethal"]
    name_wardens(_DUNGEONS, {f"the_black_hollow{DEEP_BOSS_SUFFIX}": boss})
    assert (boss["hp"], boss["atk"], boss["tier"], boss["lethal"]) == (hp, atk, tier, lethal)


def test_titles_vary_across_dungeons():
    a, b = _boss(), _boss()
    b["location"] = "glacial_bastion_delve_4"
    npcs = {
        f"the_black_hollow{DEEP_BOSS_SUFFIX}": a,
        f"glacial_bastion{DEEP_BOSS_SUFFIX}": b,
    }
    name_wardens(_DUNGEONS, npcs)
    assert a["name"] != b["name"], "a region's wardens are not all 'the Warden'"


def test_a_dungeon_without_a_boss_is_skipped_and_naming_is_deterministic():
    assert name_wardens(_DUNGEONS, {}) == 0
    x, y = _boss(), _boss()
    name_wardens(_DUNGEONS, {f"the_black_hollow{DEEP_BOSS_SUFFIX}": x})
    name_wardens(_DUNGEONS, {f"the_black_hollow{DEEP_BOSS_SUFFIX}": y})
    assert x["name"] == y["name"] and x["keywords"] == y["keywords"]
