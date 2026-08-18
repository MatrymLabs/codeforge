"""CARD: delivery -- generate 'carry a parcel from town A to town B' contracts (a courier quest).

Errands send a courier to ONE place; a delivery is the two-beat staple: pick a parcel UP in one town
and hand it OVER in another. This forges those between neighbouring towns -- each town consigns
a parcel to its trade-partner (the next up the level ladder). The quest is a real two-step arc: take
the parcel (the `on_take` trigger fires on the pickup) then arrive at the destination (`on_enter`),
so it reads as a journey with a purpose, not just a waypoint.

`generate_deliveries(settlements)` returns (quest specs, parcel items to place at the source towns).
Deterministic: the same settlements always consign the same parcels along the same routes.
"""

from __future__ import annotations

from typing import Any

from kernel.world.seed import Item, QuestSpec, QuestStep

DELIVERY_PREFIX = "delivery_"
PARCEL_PREFIX = "parcel_"  # the carried item's prototype label; on_take matches the prototype
_XP_PER_LEVEL = 12


def is_delivery(quest_id: str) -> bool:
    """Whether a quest id names a generated delivery contract (vs an errand, bounty, or arc)."""
    return quest_id.startswith(DELIVERY_PREFIX)


def _routes(settlements: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Each settlement paired with its trade-partner: the next town up the level ladder (wrapping),
    so every town consigns exactly one parcel to a distinct, level-adjacent neighbour."""
    ordered = sorted(settlements, key=lambda s: (int(s.get("level", 1)), str(s["room"])))
    n = len(ordered)
    if n < 2:  # noqa: PLR2004
        return []
    return [(ordered[i], ordered[(i + 1) % n]) for i in range(n)]


def _delivery(source: dict[str, Any], dest: dict[str, Any]) -> tuple[QuestSpec, str, Item]:
    """One courier run: a parcel item at the source town, and the two-beat quest that carries it."""
    a_room, a_name = str(source["room"]), str(source["name"])
    b_room, b_name = str(dest["room"]), str(dest["name"])
    reward = int(source.get("level", 1)) * _XP_PER_LEVEL
    parcel_label = f"{PARCEL_PREFIX}{a_room}"
    parcel = Item(
        name=f"a sealed parcel for {b_name}",
        keywords=["parcel", "package", "consignment"],
        location=f"room:{a_room}",
        slot="",
        mods={},
    )
    spec = QuestSpec(
        id=f"{DELIVERY_PREFIX}{a_room}",
        name=f"Delivery: {a_name} to {b_name}",
        start="posted",
        reward_xp=reward,
        steps=[
            QuestStep(state="posted", event="take", to="carrying", on_take=parcel_label),
            QuestStep(
                state="carrying", event="deliver", to="done", on_enter=b_room, effect="award_xp"
            ),
        ],
        terminal=["done"],
        labels={
            "posted": f"A parcel in {a_name} is bound for {b_name}. Take it up ({reward} XP).",
            "carrying": f"Carry the parcel to {b_name}.",
            "done": f"The parcel is delivered to {b_name}. The road keeps its promise.",
        },
    )
    return spec, parcel_label, parcel


def generate_deliveries(
    settlements: list[dict[str, Any]],
) -> tuple[list[QuestSpec], dict[str, Item]]:
    """One delivery per settlement, to its level-adjacent trade-partner. Returns the quest specs and
    the parcel items (by prototype label) to place at the source towns. Empty when fewer than two
    settlements exist to route between. Deterministic."""
    specs: list[QuestSpec] = []
    parcels: dict[str, Item] = {}
    for source, dest in _routes(settlements):
        spec, label, parcel = _delivery(source, dest)
        specs.append(spec)
        parcels[label] = parcel
    return specs, parcels
