"""CARD: spine -- forge the world's MAIN-ROAD quest: one guided journey through the zones in order.

The side-content generators (bounties, errands, storylines) fill the world with things to DO, but a
million-room world needs a THROUGH-LINE: the main quest that orients a new player and pulls them
across the map from the starting meadow to the endgame. This forges exactly that -- one campaign
quest, the Forgeward Road, whose beats are ARRIVING in each zone in level order. Enter the next
region and the road ticks onward, naming where to head next, until you have walked the whole world.

Unlike a side-quest it lives in the `quest` log, not the notice board: it is the spine the rest of
the content hangs on. `forge_spine(zones)` returns the single QuestSpec (or None if the world has
fewer than two zones to string together). Deterministic: the same world always lays the same road.
"""

from __future__ import annotations

from typing import Any

from parts.world.seed import QuestSpec, QuestStep

SPINE_ID = "spine_forgeward_road"
_XP_PER_CAP = 40  # the campaign payoff scales with the last zone's level cap: a whole-world reward


def is_spine(quest_id: str) -> bool:
    """Whether a quest id names the world's main-road spine (vs a side-quest or authored arc)."""
    return quest_id == SPINE_ID


def _ordered(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Zones from the starting band to the endgame, by recommended level (min then max)."""
    return sorted(zones, key=lambda z: (int(z.get("level_min") or 1), int(z.get("level_max") or 1)))


def forge_spine(zones: list[dict[str, Any]]) -> QuestSpec | None:
    """Lay the Forgeward Road: one campaign quest whose beats are entering each zone's hub (its
    first room) in level order. Returns the QuestSpec, or None if fewer than two zones exist.
    The reward lands on reaching the final zone; deterministic for a given set of zones."""
    ordered = [z for z in _ordered(zones) if z.get("rooms")]
    if len(ordered) < 2:
        return None
    names = [str(z["name"]) for z in ordered]
    reward = int(ordered[-1].get("level_max") or 1) * _XP_PER_CAP
    steps: list[QuestStep] = []
    labels: dict[str, str] = {
        "leg_0": f"The Forgeward Road runs the length of Aethryn, from {names[0]} to {names[-1]}. "
        f"Press on to {names[1]}."
    }
    last = len(ordered) - 1
    for i in range(1, len(ordered)):
        hub = str(ordered[i]["rooms"][0])
        to_state = "done" if i == last else f"leg_{i}"
        step = QuestStep(state=f"leg_{i - 1}", event=f"reach_{i}", to=to_state, on_enter=hub)
        if i == last:
            step["effect"] = "award_xp"
        steps.append(step)
        if i < last:
            labels[f"leg_{i}"] = f"You have reached {names[i]}. The road runs on to {names[i + 1]}."
    labels["done"] = (
        f"*** You have walked the Forgeward Road from {names[0]} to {names[-1]}. "
        "Aethryn is yours to roam. ***"
    )
    return QuestSpec(
        id=SPINE_ID,
        name="The Forgeward Road",
        start="leg_0",
        reward_xp=reward,
        steps=steps,
        terminal=["done"],
        labels=labels,
    )
