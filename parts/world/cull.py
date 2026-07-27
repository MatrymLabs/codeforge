"""CARD: cull -- generate 'fell N of a kind HERE' contracts at volume (the MMO's most common quest).

Bounties name ONE foe; the staple MMO quest names a KIND, a count, and a PLACE -- cull ten canids in
the Veridia Wilds. This forges those at volume: for every zone, for every creature type in its
biome, at a few count-tiers. Each is a plain chain (one step per kill), so felling N walks the quest
to done with NO counter machinery -- the state IS the tally ('s7' means seven down), persisted like
any quest.

Crucially each contract is SCOPED to its zone: a cull advances on `<zone>|<kind>`, and combat fires
that scoped event from the kill's location, so culling canids in Veridia never touches the Duskwood
board. That keeps the volume HONEST -- distinct places and types, not one quest cloned per town.
`generate_culls(zones)` returns the QuestSpecs; deterministic, so the world posts a stable board.
"""

from __future__ import annotations

from typing import Any

from parts.world.bestiary import classes_for_biome
from parts.world.seed import QuestSpec, QuestStep

CULL_PREFIX = "cull_"
_SCOPE_SEP = "|"  # a cull's trigger target is '<zone_label>|<kind>' -- combat fires the same shape
_COUNT_TIERS = (6, 12, 20)  # small / standing / great cull contracts, as a real board carries tiers


def is_cull(quest_id: str) -> bool:
    """Whether a quest id names a generated cull contract (vs a bounty, errand, or authored arc)."""
    return quest_id.startswith(CULL_PREFIX)


def scope_key(zone_label: str, kind: str) -> str:
    """The zone-scoped trigger a cull step listens on, and combat fires per keyword on a kill. One
    source of truth for the shape, so the generator and the combat hook can never drift apart."""
    return f"{zone_label}{_SCOPE_SEP}{kind}"


def _cull(zone_label: str, zone_name: str, kind: str, count: int, level: int) -> QuestSpec:
    """One zone-scoped cull: `count` identical steps, each advanced by felling a `kind` here."""
    reward = count * max(3, level // 3)
    target = scope_key(zone_label, kind)
    steps: list[QuestStep] = []
    labels: dict[str, str] = {}
    for i in range(count):
        to = "done" if i == count - 1 else f"s{i + 1}"
        step = QuestStep(state=f"s{i}", event="cull", to=to, on_cull=target)
        if i == count - 1:
            step["effect"] = "award_xp"
        steps.append(step)
        labels[f"s{i}"] = f"Cull the {kind}-kind in {zone_name}: {i}/{count} felled ({reward} XP)."
    labels["done"] = f"The {kind}-kind of {zone_name} are thinned. The region breathes easier."
    return QuestSpec(
        id=f"{CULL_PREFIX}{zone_label}_{kind}_{count}",
        name=f"Cull: {kind}-kind of {zone_name} ({count})",
        start="s0",
        reward_xp=reward,
        steps=steps,
        terminal=["done"],
        labels=labels,
    )


def generate_culls(zones: list[dict[str, Any]]) -> list[QuestSpec]:
    """One cull per (zone, creature-type of the zone's biome, count-tier). Each `zone` dict carries
    a `label` (the scope key), `name`, `biome`, and level band. A zone with no biome is skipped (no
    kinds to name). Deterministic; the volume is zones x types-per-biome x tiers, each distinct."""
    quests: list[QuestSpec] = []
    for zone in zones:
        biome = str(zone.get("biome", ""))
        label, name = str(zone.get("label", "")), str(zone.get("name", "this land"))
        if not biome or not label:
            continue
        level = int(zone.get("level_max") or zone.get("level_min") or 1)
        for kind in classes_for_biome(biome):
            for count in _COUNT_TIERS:
                quests.append(_cull(label, name, kind, count, level))
    return quests
