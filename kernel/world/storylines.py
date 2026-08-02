"""CARD: storylines -- weave a multi-beat narrative quest chain through every zone that has one.

Bounties (kill a foe) and errands (go to a place) gave the world side-quests at VOLUME, but each is
a single beat. An MMORPG zone also carries a STORY: a small arc that threads the area's real
geography into one tale. This is that depth. For every zone that pairs a home town with a dungeon,
`generate_storylines` forges a three-beat chain out of the world's own features:

    reach the zone's dungeon  ->  slay its deep terror  ->  bear word home to the town, for reward

Each beat fires from a REAL world action (the quest engine's on_enter / on_defeat triggers), so the
tale advances by playing, not by menu. The chain starts already afoot, so it advertises itself on
the notice board (a `Tales:` group) with a hook the moment a player reads the board. Deterministic
systemic: it reaches narrative DEPTH the way the generators reach room and creature volume -- not
hand-crafted WoW prose, but a genuine zone arc on every zone the map can support one.
"""

from __future__ import annotations

from typing import Any

from kernel.world.seed import QuestSpec, QuestStep

STORY_PREFIX = "story_"
_XP_PER_LEVEL = 25  # a zone capstone pays well: it is a chain of beats, not a single deed
DEEP_BOSS_SUFFIX = (
    "_deep_boss"  # the delve generator names each dungeon's deep boss `<room>_deep_boss`
)


def is_storyline(quest_id: str) -> bool:
    """Whether a quest id names a generated zone storyline (vs a bounty, errand, or arc)."""
    return quest_id.startswith(STORY_PREFIX)


def _storyline(
    town_room: str, town: str, dungeon_room: str, dungeon: str, region: str, cap: int
) -> QuestSpec:
    """One zone arc: afoot at the town, into the dungeon, slay its boss, home for reward."""
    reward = cap * _XP_PER_LEVEL
    boss = f"{dungeon_room}{DEEP_BOSS_SUFFIX}"
    return QuestSpec(
        id=f"{STORY_PREFIX}{town_room}",
        name=f"The Tale of {town}",
        start="afoot",
        reward_xp=reward,
        steps=[
            QuestStep(state="afoot", event="reach", to="at_heart", on_enter=dungeon_room),
            QuestStep(state="at_heart", event="slay", to="homeward", on_defeat=boss),
            QuestStep(
                state="homeward", event="deliver", to="done", on_enter=town_room, effect="award_xp"
            ),
        ],
        terminal=["done"],
        labels={
            "afoot": f"A tale of {region}: {dungeon} festers, and {town} lives in its shadow.",
            "at_heart": f"You stand within {dungeon}. Its deep terror waits below. Fell it.",
            "homeward": f"The terror of {dungeon} is slain. Bear word to {town} ({reward} XP).",
            "done": f"*** {town} breathes free. {region} will remember you. ***",
        },
    )


def _room_of(entry: dict[str, Any]) -> str:
    return str(entry["room"])


def generate_storylines(
    zones: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    dungeons: list[dict[str, Any]],
) -> list[QuestSpec]:
    """One narrative chain per zone that HAS BOTH a home town and a dungeon among its rooms. `zones`
    is a list of zone dicts ({name, region, rooms, level_max, ...}); `settlements` and `dungeons`
    are the same {room, name, ...} lists the world assembly already holds. A zone missing either a
    town or a dungeon simply gets no tale (honest: not every area can carry one). Deterministic."""
    towns = {_room_of(s): s for s in settlements}
    delves = {_room_of(d): d for d in dungeons}
    tales: list[QuestSpec] = []
    for zone in zones:
        rooms = zone.get("rooms") or []
        town = next((towns[r] for r in rooms if r in towns), None)
        dungeon = next((delves[r] for r in rooms if r in delves), None)
        if town is None or dungeon is None:
            continue
        region = str(zone.get("region") or zone.get("name") or "the land")
        cap = int(zone.get("level_max") or town.get("level") or 1)
        tales.append(
            _storyline(
                _room_of(town),
                str(town["name"]),
                _room_of(dungeon),
                str(dungeon["name"]),
                region,
                cap,
            )
        )
    return tales
