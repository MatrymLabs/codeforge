"""Test twin for kernel/world/dungeon_crawl.py -- 'descend to the heart of a dungeon' contracts.

Acceptance: each dungeon posts one two-beat descent -- cross the mouth, then reach the deep boss's
chamber for the reward. It targets the delve's own geography. Refusal: no dungeons, no crawls.
"""

from __future__ import annotations

from kernel.world.delve import boss_chamber
from kernel.world.dungeon_crawl import CRAWL_PREFIX, generate_crawls, is_dungeon_crawl

_DUNGEONS = [
    {"room": "the_black_hollow", "name": "The Black Hollow", "level": 50},
    {"room": "glacial_bastion", "name": "Glacial Bastion", "level": 90},
]


def test_one_crawl_per_dungeon():
    crawls = generate_crawls(_DUNGEONS)
    assert len(crawls) == len(_DUNGEONS) and all(is_dungeon_crawl(c["id"]) for c in crawls)
    assert {c["id"] for c in crawls} == {
        f"{CRAWL_PREFIX}the_black_hollow",
        f"{CRAWL_PREFIX}glacial_bastion",
    }


def test_the_descent_crosses_the_mouth_then_reaches_the_boss_chamber():
    crawl = next(c for c in generate_crawls(_DUNGEONS) if c["id"].endswith("the_black_hollow"))
    cross, reach = crawl["steps"]
    assert cross["on_enter"] == "the_black_hollow", "beat 1 crosses the dungeon mouth"
    assert reach["on_enter"] == boss_chamber("the_black_hollow"), (
        "beat 2 reaches the deepest chamber"
    )
    assert reach["effect"] == "award_xp" and cross.get("effect") is None


def test_reward_scales_with_dungeon_level():
    a, b = generate_crawls(_DUNGEONS)
    assert b["reward_xp"] > a["reward_xp"], "the deeper (higher-level) dungeon pays more"


def test_no_dungeons_yields_no_crawls_and_forging_is_deterministic():
    assert generate_crawls([]) == []
    assert generate_crawls(_DUNGEONS) == generate_crawls(_DUNGEONS)
