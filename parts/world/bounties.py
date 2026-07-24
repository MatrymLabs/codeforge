"""CARD: bounties -- generate hunt-contracts from the world's foes (side-content, at volume).

Hand-authoring hundreds of side-quests is the AAA content mountain; this is the generation lever
(compare parts.world.spiral for the world, parts.shelf.affixes for loot) pointed at quests. Every
combatant, levelled foe becomes a one-step BOUNTY: "fell it, collect the reward." Deterministic --
the same seed foes yield the same board -- and the output is real, trackable quests on the multi-
quest engine, not flavour text. It reaches side-quest VOLUME; it is systemic, not hand-crafted.

`generate_bounties(npcs)` returns QuestSpecs (id `bounty_<foe>`) the quest loader folds in alongside
authored arcs; the `contracts` verb lists them so they do not flood the story-quest view.
"""

from __future__ import annotations

from parts.world.seed import Npc, QuestSpec, QuestStep

BOUNTY_PREFIX = "bounty_"
_XP_PER_LEVEL = 12  # a bounty's reward = foe level x this (a levelled foe is a worthier contract)


def is_bounty(quest_id: str) -> bool:
    """Whether a quest id names a generated bounty (vs a hand-authored story arc)."""
    return quest_id.startswith(BOUNTY_PREFIX)


def _bounty_for(foe_id: str, foe: Npc) -> QuestSpec:
    """One hunt-contract for a foe: posted -> collected on its defeat, awarding XP by its level."""
    level = int(foe.get("level", 1))
    reward = level * _XP_PER_LEVEL
    name = foe["name"]
    step = QuestStep(
        state="posted", event="collect", to="collected", on_defeat=foe_id, effect="award_xp"
    )
    return QuestSpec(
        id=f"{BOUNTY_PREFIX}{foe_id}",
        name=f"Bounty: {name}",
        start="posted",
        reward_xp=reward,
        steps=[step],
        terminal=["collected"],
        labels={
            "posted": f"A bounty stands on {name} (level {level}). Fell it for {reward} XP.",
            "collected": f"Bounty collected: {name} is felled. Well hunted.",
        },
    )


def generate_bounties(npcs: dict[str, Npc]) -> list[QuestSpec]:
    """A bounty for every COMBATANT, LEVELLED foe (hp > 0 and a declared level), in id order.

    Levelless training foes and peaceful NPCs get no contract -- a bounty must name a real threat.
    Deterministic: same foes in, same board out."""
    bounties = []
    for foe_id in sorted(npcs):
        foe = npcs[foe_id]
        if foe.get("hp", 0) > 0 and foe.get("level"):
            bounties.append(_bounty_for(foe_id, foe))
    return bounties
