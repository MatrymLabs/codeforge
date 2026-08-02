"""CARD: delve_sets -- a matched gear SET per dungeon, dropped across its delve.

The armory drops single pieces and relics forge one legendary per boss, but an MMORPG dungeon has a
SET: clear the whole delve, wear the matched loadout, earn a bonus beyond the pieces. This forges
that. For each dungeon it forges three themed armour pieces (head/body/arm, distinct slots so they
wear together) named for the dungeon, hangs one on each of the delve's three trash foes as a
guaranteed drop, and declares a GearSet whose bonus fires when all three are worn. So the descent
itself is the collection: three chambers, three pieces, one set at the end (the boss's relic is a
separate prize on top).

`forge_delve_sets(dungeons, npcs)` mutates the trash foes' drops in place and returns (item
prototypes to merge into ITEMS, the GearSets to register with gearsets). Deterministic and pure: the
same dungeon always yields the same set, reproducible like the rest of the generators.
"""

from __future__ import annotations

from typing import Any

from kernel.world.relics import (
    iconic_word,
)  # the same dungeon word the relic borrows, for a matched name
from kernel.world.seed import GearSet, Item, Npc

SET_PREFIX = "delveset_"
# The three pieces of a delve set: (slot, the derived stat its own mod raises, a noun for its name).
# Distinct slots (head/body/arm) so the set wears together; the boss relic takes weapon/accessory.
_PIECES: tuple[tuple[str, str, str], ...] = (
    ("head", "DEF", "helm"),
    ("body", "DEF", "hauberk"),
    ("arm", "EVA", "bracers"),
)


def is_delve_set_piece(item_label: str) -> bool:
    """Whether an item label names a generated delve-set piece (vs generic gear or a relic)."""
    return item_label.startswith(SET_PREFIX)


def _piece(
    dungeon_room: str, core: str, level: int, slot: str, stat: str, noun: str
) -> tuple[str, Item]:
    """One armour piece of a dungeon's set: named for the dungeon, statted to its level band."""
    amount = max(2, level // 7)  # a solid floor; the set BONUS is the reason to collect all three
    item = Item(
        name=f"the {core} {noun}",
        keywords=[core.lower(), noun, "gear"],
        location="nowhere",  # a drop-only prototype: cloned onto the floor when the foe falls
        slot=slot,
        mods={stat: amount},
        rarity="epic",
    )
    return f"{SET_PREFIX}{dungeon_room}_{slot}", item


def forge_delve_sets(
    dungeons: list[dict[str, Any]], npcs: dict[str, Npc]
) -> tuple[dict[str, Item], dict[str, GearSet]]:
    """Forge a three-piece set per dungeon, hang one piece on each of its three delve trash foes,
    and declare the set's bonus. Mutates the foes' `drops`; returns (item prototypes, gear sets). A
    dungeon missing a trash foe drops that piece (a set still needs >= 2 pieces to form)."""
    items: dict[str, Item] = {}
    sets: dict[str, GearSet] = {}
    for dungeon in dungeons:
        room = str(dungeon["room"])
        core = iconic_word(room)
        level = int(dungeon.get("level") or 1)
        pieces: list[str] = []
        for depth, (slot, stat, noun) in enumerate(_PIECES, start=1):
            foe = npcs.get(f"{room}_delve_{depth}_foe")
            if foe is None:  # this delve is shallower than expected; skip this piece
                continue
            label, item = _piece(room, core, level, slot, stat, noun)
            items[label] = item
            drops = list(foe.get("drops") or [])
            if label not in drops:
                drops.append(label)
            foe["drops"] = drops
            pieces.append(label)
        if len(pieces) < 2:  # a set needs at least two pieces to be worth collecting
            continue
        name = str(dungeon["name"])
        title = f"{name} set" if name.lower().startswith("the ") else f"the {name} set"
        sets[f"{SET_PREFIX}{room}"] = GearSet(
            name=title,
            pieces=pieces,
            bonus={"DEF": max(2, level // 10), "EVA": max(1, level // 20)},
        )
    return items, sets
