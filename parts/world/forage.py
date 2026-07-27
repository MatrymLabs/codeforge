"""CARD: forage -- generate 'gather N of a material' contracts (the non-combat volume archetype).

The cull board fills the world with things to KILL; a forager needs the same at the gathering node.
This forges 'gather N of a material' contracts at volume: for every zone, for every material its
biome's nodes yield, at a couple of count-tiers. Like a cull it is a plain N-step chain -- one step
per harvest -- so gathering N walks it to done with NO counter engine, the state its own tally.

Each contract is SCOPED to its zone (shares cull.scope_key): a forage advances on `<zone>|<mat>`,
and the gather action fires that scoped event from the node's location, so working ember in Veridia
never fills the Frostspire board. `generate_forages(zones)` returns the QuestSpecs, deterministic.
"""

from __future__ import annotations

from typing import Any

from parts.world.cull import scope_key
from parts.world.seed import QuestSpec, QuestStep
from parts.world.wildlands import gatherable_materials

FORAGE_PREFIX = "forage_"
_COUNT_TIERS = (5, 10)  # foraging is steadier than the hunt: fewer tiers, smaller counts


def is_forage(quest_id: str) -> bool:
    """Whether a quest id names a generated forage contract (vs a cull, bounty, or authored arc)."""
    return quest_id.startswith(FORAGE_PREFIX)


def _pretty(material: str) -> str:
    """A material prototype label as readable words: 'ember_shard' -> 'ember shard'."""
    return material.replace("_", " ")


def _forage(zone_label: str, zone_name: str, material: str, count: int, level: int) -> QuestSpec:
    """One zone-scoped forage: `count` identical steps, each advanced by gathering the material."""
    reward = count * max(2, level // 4)
    target = scope_key(zone_label, material)
    name = _pretty(material)
    steps: list[QuestStep] = []
    labels: dict[str, str] = {}
    for i in range(count):
        to = "done" if i == count - 1 else f"s{i + 1}"
        step = QuestStep(state=f"s{i}", event="forage", to=to, on_forage=target)
        if i == count - 1:
            step["effect"] = "award_xp"
        steps.append(step)
        labels[f"s{i}"] = f"Gather {name} in {zone_name}: {i}/{count} ({reward} XP)."
    labels["done"] = f"You have gathered {name} enough for {zone_name}'s makers."
    return QuestSpec(
        id=f"{FORAGE_PREFIX}{zone_label}_{material}_{count}",
        name=f"Forage: {name} of {zone_name} ({count})",
        start="s0",
        reward_xp=reward,
        steps=steps,
        terminal=["done"],
        labels=labels,
    )


def generate_forages(zones: list[dict[str, Any]]) -> list[QuestSpec]:
    """One forage per (zone, material its biome yields, count-tier). Each `zone` dict carries a
    `label`, `name`, `biome`, and level band. A zone with no biome is skipped. Deterministic; the
    volume is zones x materials-per-biome x tiers, each distinct and place-scoped."""
    quests: list[QuestSpec] = []
    for zone in zones:
        biome = str(zone.get("biome", ""))
        label, name = str(zone.get("label", "")), str(zone.get("name", "this land"))
        if not biome or not label:
            continue
        level = int(zone.get("level_max") or zone.get("level_min") or 1)
        for material in gatherable_materials(biome):
            for count in _COUNT_TIERS:
                quests.append(_forage(label, name, material, count, level))
    return quests
