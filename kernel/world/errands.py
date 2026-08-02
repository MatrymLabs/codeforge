"""CARD: errands -- generate travel side-quests across the map (side-content variety, at volume).

Bounties (kernel.world.bounties) gave the world kill-quests at volume; this gives it other staple
of an MMORPG notice board: ERRANDS -- go somewhere and do a small deed. Each settlement posts one
errand that sends the player to a distinct destination on the map (a neighbouring town, a dungeon
mouth, or a waystone hub), completed by ARRIVING there (the quest engine's `on_enter` trigger). The
flavour varies with the destination -- carry word to a town, scout a dungeon, bear a token
to a waystone -- so a board of them reads as many small tasks, not one repeated.

Every errand targets a DIFFERENT room, so the on_enter triggers never collide (unlike an item);
the reward scales with the poster's level band. Deterministic and systemic (not hand-crafted): it
reaches side-quest VOLUME the way bounties do, on the same multi-quest engine, and shows on the same
`contracts` notice board.
"""

from __future__ import annotations

from typing import Any

from kernel.world.seed import QuestSpec, QuestStep

ERRAND_PREFIX = "errand_"
_XP_PER_LEVEL = 15  # an errand pays a touch more than a bounty: it costs travel, not just a fight

# The flavour an errand takes, chosen by the destination's kind. {name} is the destination.
_FLAVOUR: dict[str, tuple[str, str]] = {
    "town": ("Carry word to {name}", "You bring word to {name}. It is gratefully received."),
    "dungeon": ("Scout the approach to {name}", "You reach {name} and mark the way. Well scouted."),
    "hub": ("Bear a waystone-token to {name}", "You set the token at {name}. The stone answers."),
}


def is_errand(quest_id: str) -> bool:
    """Whether a quest id names a generated errand (vs a bounty or a hand-authored arc)."""
    return quest_id.startswith(ERRAND_PREFIX)


def _errand(source_room: str, dest_room: str, dest_name: str, kind: str, level: int) -> QuestSpec:
    """One travel-errand: posted at a settlement, completed by ARRIVING at the destination room."""
    reward = level * _XP_PER_LEVEL
    task, done = _FLAVOUR.get(kind, _FLAVOUR["town"])
    task, done = task.format(name=dest_name), done.format(name=dest_name)
    return QuestSpec(
        id=f"{ERRAND_PREFIX}{source_room}",
        name=f"Errand: {dest_name}",
        start="posted",
        reward_xp=reward,
        steps=[
            QuestStep(
                state="posted", event="arrive", to="done", on_enter=dest_room, effect="award_xp"
            )
        ],
        terminal=["done"],
        labels={
            "posted": f"{task} ({reward} XP).",
            "done": done,
        },
    )


def generate_errands(
    settlements: list[dict[str, Any]], destinations: list[dict[str, Any]]
) -> list[QuestSpec]:
    """One errand per settlement, to a DISTINCT destination (round-robin over
    `destinations`, skipping the poster's own room). `destinations` is a list of {room, name, kind}.
    Deterministic; empty if there is nowhere to send anyone."""
    if not settlements or not destinations:
        return []
    quests: list[QuestSpec] = []
    used: set[str] = set()
    pool = destinations
    n = len(pool)
    for i, town in enumerate(settlements):
        source = town["room"]
        level = int(town["level"])
        # walk the pool from an offset until we find a distinct, unused destination
        dest = None
        for step in range(n):
            cand = pool[(i + step) % n]
            if cand["room"] != source and cand["room"] not in used:
                dest = cand
                break
        if dest is None:  # more settlements than distinct destinations: reuse is fine past that
            dest = next((c for c in pool if c["room"] != source), None)
            if dest is None:
                continue
        used.add(dest["room"])
        quests.append(_errand(source, dest["room"], str(dest["name"]), str(dest["kind"]), level))
    return quests
