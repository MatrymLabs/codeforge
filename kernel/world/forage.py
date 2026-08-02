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

from kernel.world.cull import scope_key
from kernel.world.seed import QuestSpec, QuestStep
from kernel.world.wildlands import gatherable_materials

FORAGE_PREFIX = "forage_"
_COUNT_TIERS = (5, 10)  # foraging is steadier than the hunt: fewer tiers, smaller counts

# Presentation flavour (the same idea as cull's): the gather MECHANIC is fixed, but a board of 176
# identical "Forage: X of Y" lines reads as filler. Each contract draws a framing per (zone,
# material), a tier word per count, and a region-toned close per biome. Id, scope, steps, reward
# are untouched -- only the words change.
_FRAMINGS = (
    ("Forage", "Gather", "gathered"),
    ("Harvest", "Harvest", "harvested"),
    ("Collection", "Collect", "brought in"),
    ("Requisition", "Bring in", "requisitioned"),
    ("Provision", "Lay in", "laid in"),
    ("Haul", "Haul in", "hauled in"),
    ("Gleaning", "Glean", "gleaned"),
    ("Draw", "Draw", "drawn"),
)
_TIER_WORD = {5: "A small", 10: "A standing"}
_BIOME_TONE = {
    "temperate-meadow": "The village makers will put it to use.",
    "wild-forest": "The wood's craftfolk have what they need.",
    "glacier-waste": "The hold's smiths will not want for it.",
    "salt-desert": "The caravan traders will pay well for it.",
    "living-jungle": "The physicians can work with this.",
    "coastal-strand": "The harbour makers are glad of it.",
    "volcanic-flats": "The forge-crews can feed the fires now.",
}


def is_forage(quest_id: str) -> bool:
    """Whether a quest id names a generated forage contract (vs a cull, bounty, or authored arc)."""
    return quest_id.startswith(FORAGE_PREFIX)


def _pretty(material: str) -> str:
    """A material prototype label as readable words: 'ember_shard' -> 'ember shard'."""
    return material.replace("_", " ")


def _framing(zone_label: str, material: str) -> tuple[str, str, str]:
    """A stable framing for this (zone, material): a deterministic char-sum index (PYTHONHASHSEED-
    immune), so the board reads varied but a given contract never changes its face."""
    idx = (sum(ord(c) for c in zone_label) + sum(ord(c) for c in material)) % len(_FRAMINGS)
    return _FRAMINGS[idx]


def _forage(
    zone_label: str, zone_name: str, material: str, count: int, level: int, biome: str = ""
) -> QuestSpec:
    """One zone-scoped forage: `count` identical steps, each advanced by gathering the material. The
    mechanic is fixed; the words are dressed with a per-(zone,material) framing, a tier word, and a
    region-toned close, so the board reads varied rather than 176 clones."""
    reward = count * max(2, level // 4)
    target = scope_key(zone_label, material)
    name = _pretty(material)
    title, verb, done_word = _framing(zone_label, material)
    tier = _TIER_WORD.get(count, "A")
    tone = _BIOME_TONE.get(biome, "The region's makers will put it to use.")
    steps: list[QuestStep] = []
    labels: dict[str, str] = {}
    for i in range(count):
        to = "done" if i == count - 1 else f"s{i + 1}"
        step = QuestStep(state=f"s{i}", event="forage", to=to, on_forage=target)
        if i == count - 1:
            step["effect"] = "award_xp"
        steps.append(step)
        labels[f"s{i}"] = f"{verb} {name} in {zone_name}: {i}/{count} ({reward} XP)."
    labels["done"] = f"You have {done_word} {name} enough for {zone_name}. {tone}"
    return QuestSpec(
        id=f"{FORAGE_PREFIX}{zone_label}_{material}_{count}",
        name=f"{tier} {title}: {name} of {zone_name}",
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
                quests.append(_forage(label, name, material, count, level, biome))
    return quests
