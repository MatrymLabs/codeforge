"""CARD: landmarks -- raise a readable monument in every zone's hub (surface storytelling).

Dungeon inscriptions tell a story at the DEPTHS; a region needs one at the SURFACE too -- the
weathered monument at the heart of a zone that tells arrivals where they are, who this land is for,
and what festers at its edge. This raises exactly that: one readable monument in each zone's hub
(its first room), its words naming the region, its recommended level band, and (when the zone holds
a dungeon) the terror that lurks there. So walking into a new region reads as an arrival, not just
another room, and the monument points a player on -- the surface twin of the depths' inscription.

`raise_landmarks(zones, dungeons)` returns the placed monument items to merge into ITEMS once the
world is assembled (their rooms are the zone hubs, which load_zones already proved exist in WORLD).
Deterministic and pure: the same zone always raises the same monument, like the other generators.
"""

from __future__ import annotations

from typing import Any

from kernel.world.seed import Item

LANDMARK_PREFIX = "landmark_"


def is_landmark(item_label: str) -> bool:
    """Whether an item label names a generated zone monument (vs authored lore or loot)."""
    return item_label.startswith(LANDMARK_PREFIX)


def _dungeon_in(zone: dict[str, Any], dungeons: list[dict[str, Any]]) -> str | None:
    """The name of a dungeon whose room sits in this zone, or None if the zone holds none."""
    rooms = set(zone.get("rooms") or [])
    return next((str(d["name"]) for d in dungeons if str(d["room"]) in rooms), None)


def raise_landmark(zone: dict[str, Any], dungeons: list[dict[str, Any]]) -> tuple[str, Item] | None:
    """Raise one zone's monument: a readable item in its hub (first room), its words naming the
    region, its level band, and any dungeon within. Returns (label, item), or None for a hubless
    zone. Deterministic."""
    rooms = zone.get("rooms") or []
    if not rooms:
        return None
    hub = str(rooms[0])
    name = str(zone.get("name") or "this land")
    region = str(zone.get("region") or name)
    lo, hi = int(zone.get("level_min") or 1), int(zone.get("level_max") or 1)
    words = f"{name}, in the reach of {region}. A land for heroes of level {lo} to {hi}."
    peril = _dungeon_in(zone, dungeons)
    if peril:
        words += f" Beware {peril}, which festers at its edge."
    item = Item(
        name="a weathered monument",
        keywords=["monument", "landmark", "stone"],
        location=f"room:{hub}",
        slot="",  # a standing stone, not gear: it is read, not worn
        mods={},
        lore=words,
    )
    return f"{LANDMARK_PREFIX}{hub}", item


def raise_landmarks(zones: list[dict[str, Any]], dungeons: list[dict[str, Any]]) -> dict[str, Item]:
    """One readable monument per zone, placed in its hub. Returns the items to merge into ITEMS once
    the world is assembled (the hubs already exist in it). Deterministic; a hubless zone is skipped,
    and two zones sharing a hub keep just one monument (last wins, harmlessly)."""
    raised: dict[str, Item] = {}
    for zone in zones:
        made = raise_landmark(zone, dungeons)
        if made is not None:
            label, item = made
            raised[label] = item
    return raised
