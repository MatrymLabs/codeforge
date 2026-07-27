"""CARD: inscriptions -- carve a readable lore inscription into every dungeon's deepest chamber.

The delve sinks a descent below each dungeon mouth and the deep boss waits at the bottom, but the
depths tell no story. An AAA dungeon has environmental STORYTELLING: a carving on the wall naming
what was sealed here and warning you off. This carves exactly that -- one readable inscription in
each dungeon's boss chamber, naming that dungeon AND the signature relic it guards (the same name
parts.world.relics forges), so the discovery loop closes: a town rumour points you here, the
inscription confirms the prize at the depths, and felling the boss claims it.

`carve_inscription` returns one placed lore item; `carve_inscriptions(dungeons)` returns them all to
merge into ITEMS before the boot link-audit (their rooms are the delve chambers, already generated).
Deterministic and pure: the same dungeon always bears the same words, reproducible like the rest.
"""

from __future__ import annotations

from typing import Any

from parts.world.delve import boss_chamber
from parts.world.relics import forge_relic
from parts.world.seed import Item

INSCRIPTION_PREFIX = "inscription_"

# The carving's words, chosen by dungeon index so the depths vary. Each names the {dungeon} and the
# {relic} it guards, so an inscription is environmental confirmation of a town's rumour.
_LORE: tuple[str, ...] = (
    "Carved in {dungeon}: 'Here we bound {relic} and its keeper. Wake neither.'",
    "Scratched in {dungeon}: 'We came for {relic}. Only the dark went home.'",
    "A warding-mark in {dungeon}: 'What holds {relic} does not sleep. It waits.'",
    "Runes in {dungeon}: 'The {relic} is the lure, the terror the trap. Turn back.'",
)


def is_inscription(item_label: str) -> bool:
    """Whether an item label names a generated dungeon inscription (vs authored lore or loot)."""
    return item_label.startswith(INSCRIPTION_PREFIX)


def carve_inscription(
    dungeon_room: str, dungeon_name: str, level: int, idx: int
) -> tuple[str, Item]:
    """Carve one dungeon's inscription: a readable, unequippable item lying in its boss chamber, its
    words naming the dungeon and the relic it guards. Returns (label, item). Deterministic."""
    _, relic = forge_relic(dungeon_room, dungeon_name, level, idx)
    words = _LORE[idx % len(_LORE)].format(dungeon=dungeon_name, relic=relic["name"])
    item = Item(
        name="a worn inscription",
        keywords=["inscription", "carving", "wall"],
        location=f"room:{boss_chamber(dungeon_room)}",
        slot="",  # a wall carving, not gear: it is read, not worn
        mods={},
        lore=words,
    )
    return f"{INSCRIPTION_PREFIX}{dungeon_room}", item


def carve_inscriptions(dungeons: list[dict[str, Any]]) -> dict[str, Item]:
    """One readable inscription per dungeon, placed in its boss chamber. Returns the items to merge
    into ITEMS before the link-audit (the chambers exist from generate_delves). Index matches
    relics.arm_deep_bosses, so the relic an inscription names is the real one."""
    carved: dict[str, Item] = {}
    for idx, dungeon in enumerate(dungeons):
        room = str(dungeon["room"])
        level = int(dungeon.get("level") or 1)
        label, item = carve_inscription(room, str(dungeon["name"]), level, idx)
        carved.setdefault(label, item)
    return carved
