"""CARD: rumors -- seed town residents with gossip that points at real nearby content (discovery).

Townsfolk shipped with generic small talk (their trade, "a good place to rest"). An AAA world's NPCs
talk about the WORLD: they name the dungeon over the hill, the terror in its depths, and the prize
it guards -- a discovery layer that turns a plaza of extras into signposts toward content. This
seeds exactly that. For every settlement in a zone that holds a dungeon, each resident gains a
`rumor` topic (and a rumour woven into their greeting) that names that dungeon AND the signature
relic waiting in it (the same name parts.world.relics forges), so `ask <folk> about rumor` guides.

`seed_rumors(town_npcs, zones, dungeons)` MUTATES the residents in place (adding the topic) and
returns how many it touched. Deterministic and pure: the same town always tells the same tale, drawn
from the world's own geography and loot, reproducible like the other generators.
"""

from __future__ import annotations

from typing import Any

from parts.world.relics import forge_relic
from parts.world.seed import Npc

# Rumour lines, chosen by the resident's index so a town's crowd varies. Each names the {dungeon}
# and the {relic} it guards, so any resident is a signpost toward the same nearby content.
_RUMOURS: tuple[str, ...] = (
    "They whisper that {relic} lies deep in {dungeon}, past a terror none have felled.",
    "Adventurers go into {dungeon} chasing {relic}. Not all of them come back.",
    "If you have the steel for it, {dungeon} guards {relic} at its black heart.",
    "The old tales say {relic} was lost in {dungeon}. Its deep terror keeps it still.",
)


def _room_of(entry: dict[str, Any]) -> str:
    return str(entry["room"])


def _zone_dungeon(
    zones: list[dict[str, Any]], dungeons: list[dict[str, Any]]
) -> dict[str, tuple[dict[str, Any], int]]:
    """Map every room in a zone that holds a dungeon to that (dungeon, its index in `dungeons`). The
    index matches relics.arm_deep_bosses, so the relic name a rumour tells is the real one."""
    by_room = {_room_of(d): (d, i) for i, d in enumerate(dungeons)}
    reach: dict[str, tuple[dict[str, Any], int]] = {}
    for zone in zones:
        rooms = zone.get("rooms") or []
        found = next((by_room[r] for r in rooms if r in by_room), None)
        if found is None:
            continue
        for room in rooms:
            reach[str(room)] = found
    return reach


def seed_rumors(
    town_npcs: dict[str, Npc],
    zones: list[dict[str, Any]],
    dungeons: list[dict[str, Any]],
) -> int:
    """Give each resident of a dungeon-bearing zone a `rumor` topic (and a woven greeting) naming
    the dungeon and the relic it guards. Mutates `town_npcs` in place; returns the residents
    touched. A town in a zone with no dungeon is left with its plain small talk (honest silence)."""
    reach = _zone_dungeon(zones, dungeons)
    seeded = 0
    for idx, npc in enumerate(town_npcs.values()):
        found = reach.get(str(npc.get("location", "")))
        if found is None or npc.get("shop"):  # a merchant keeps to its wares; only folk gossip
            continue
        dungeon, d_idx = found
        level = int(dungeon.get("level") or 1)
        _, relic = forge_relic(_room_of(dungeon), str(dungeon["name"]), level, d_idx)
        line = _RUMOURS[idx % len(_RUMOURS)].format(dungeon=dungeon["name"], relic=relic["name"])
        topics = npc.get("topics") or {}
        topics["rumor"] = [line]
        npc["topics"] = topics
        npc["dialogue"] = [*npc.get("dialogue", []), f'They lean in. "{line}"']
        seeded += 1
    return seeded
