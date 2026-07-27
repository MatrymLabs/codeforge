"""CARD: dungeon_crawl -- generate 'descend to the heart of a dungeon' contracts (exploration).

A cull rewards killing, a delivery rewards travelling; a dungeon crawl rewards DEPTH -- reaching the
bottom of a delve at all. This forges one per dungeon: a two-beat descent that fires when the player
crosses the mouth and again when they stand in the deep boss's chamber, paying out for having braved
the descent (the boss's fall and its relic are a separate prize on top). It reuses the delve's own
geography -- `delve.boss_chamber` names the target -- and the `on_enter` trigger, no new machinery.

`generate_crawls(dungeons)` returns the QuestSpecs. Deterministic: the same dungeons always post the
same descents.
"""

from __future__ import annotations

from typing import Any

from parts.world.delve import boss_chamber
from parts.world.seed import QuestSpec, QuestStep

CRAWL_PREFIX = "crawl_"
_XP_PER_LEVEL = 20  # a whole descent pays well: it is deep and dangerous


def is_dungeon_crawl(quest_id: str) -> bool:
    """Whether a quest id names a generated dungeon-crawl contract (vs a storyline or bounty)."""
    return quest_id.startswith(CRAWL_PREFIX)


def _crawl(dungeon: dict[str, Any]) -> QuestSpec:
    """One dungeon's descent: cross the mouth, then reach the deep boss's chamber for the reward."""
    mouth, name = str(dungeon["room"]), str(dungeon["name"])
    level = int(dungeon.get("level") or 1)
    reward = level * _XP_PER_LEVEL
    return QuestSpec(
        id=f"{CRAWL_PREFIX}{mouth}",
        name=f"Descent: {name}",
        start="above",
        reward_xp=reward,
        steps=[
            QuestStep(state="above", event="enter", to="delving", on_enter=mouth),
            QuestStep(
                state="delving",
                event="reach",
                to="done",
                on_enter=boss_chamber(mouth),
                effect="award_xp",
            ),
        ],
        terminal=["done"],
        labels={
            "above": f"They say none walk the full depth of {name}. Cross its mouth and descend.",
            "delving": f"You are within {name}. Press on to its deepest chamber.",
            "done": f"You have reached the heart of {name} and lived. Few can ({reward} XP).",
        },
    )


def generate_crawls(dungeons: list[dict[str, Any]]) -> list[QuestSpec]:
    """One descent per dungeon, keyed off its mouth and its deep boss's chamber. Deterministic;
    empty when the world ships no dungeons."""
    return [_crawl(d) for d in dungeons]
