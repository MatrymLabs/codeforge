"""CARD: relics -- forge one SIGNATURE legendary drop for every dungeon's deep boss (loot payoff).

The armory arms every guardian with generic forged gear, and the affix factory rolls rarity on it at
drop time -- good LOOT VOLUME, but a deep boss deserves a memorable REWARD, the AAA hook that makes
felling one an event ("the Black Hollow drops the Black Fang"). This forges exactly that: one named,
hand-feeling LEGENDARY relic per dungeon, guaranteed on its deep boss in ADDITION to the generic
drop. Each relic is iconic (a name drawn from its dungeon), strong (a legendary floor, not an affix
gamble), readable (a `lore` line about the terror it was torn from), and equippable like any gear.

`forge_relic` returns one prototype; `arm_deep_bosses(dungeons, npcs)` attaches each dungeon's relic
to its `<room>_deep_boss` and returns the prototypes to merge into the item table. Deterministic and
pure: the same dungeon always yields the same relic, reproducible like the rest of the generators.
"""

from __future__ import annotations

from typing import Any

from parts.world.seed import Item, Npc

RELIC_PREFIX = "relic_"
DEEP_BOSS_SUFFIX = (
    "_deep_boss"  # the delve generator names each dungeon's deep boss `<room>_deep_boss`
)
_ARTICLES = {
    "the",
    "of",
    "a",
    "an",
}  # skipped when picking a relic's iconic word from a dungeon name

# Each slot lends the relic a primary stat, a lesser secondary, and a pool of iconic relic-nouns. A
# dungeon's index picks the slot, so a region's relics spread across weapons, armour, and trinkets.
_SLOTS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("weapon", "ATK", "ACC", ("Fang", "Edge", "Bane", "Reaver")),
    ("body", "DEF", "ATK", ("Aegis", "Shroud", "Carapace")),
    ("head", "DEF", "ACC", ("Crown", "Visage", "Gaze")),
    ("arm", "DEF", "EVA", ("Grasp", "Gauntlet", "Talon")),
    ("accessory_1", "ACC", "ATK", ("Heart", "Eye", "Ember")),
    ("accessory_2", "EVA", "DEF", ("Sigil", "Whisper", "Knot")),
)


def is_relic(item_label: str) -> bool:
    """Whether an item label names a generated signature relic (vs generic gear or seed loot)."""
    return item_label.startswith(RELIC_PREFIX)


def iconic_word(dungeon_room: str) -> str:
    """The evocative word a relic borrows from its dungeon (its label's first non-article word)."""
    words = [w for w in dungeon_room.split("_") if w and w not in _ARTICLES]
    return (words[0] if words else dungeon_room).capitalize()


def forge_relic(dungeon_room: str, dungeon_name: str, level: int, idx: int) -> tuple[str, Item]:
    """Forge one dungeon's signature legendary relic: named for the dungeon, slotted and statted by
    index, a legendary floor, and a lore line. Returns (label, item). Deterministic."""
    slot, primary, secondary, nouns = _SLOTS[idx % len(_SLOTS)]
    noun = nouns[(idx // len(_SLOTS)) % len(nouns)]
    core = iconic_word(dungeon_room)
    big = max(
        4, level // 2
    )  # a legendary floor: well above the generic gear the affix factory rolls
    lesser = max(2, level // 5)
    item = Item(
        name=f"the {core} {noun}",
        keywords=[core.lower(), noun.lower(), "relic"],
        location="nowhere",  # a drop-only prototype: it exists to be cloned onto the floor
        slot=slot,
        mods={primary: big, secondary: lesser},
        rarity="legendary",
        lore=f"Torn from the deep terror of {dungeon_name}. It hums with an old dark.",
    )
    return f"{RELIC_PREFIX}{dungeon_room}", item


def arm_deep_bosses(dungeons: list[dict[str, Any]], npcs: dict[str, Npc]) -> dict[str, Item]:
    """Attach each dungeon's signature relic to its deep boss as a GUARANTEED drop (added to what
    generic gear the boss already carries), and return the relic prototypes to merge into ITEMS. A
    dungeon whose deep boss is absent is skipped. Mutates each boss's `drops` in place; the returned
    prototypes must be merged before the boot link-audit runs."""
    relics: dict[str, Item] = {}
    for idx, dungeon in enumerate(dungeons):
        room = str(dungeon["room"])
        boss = npcs.get(f"{room}{DEEP_BOSS_SUFFIX}")
        if boss is None:
            continue
        level = int(boss.get("level") or dungeon.get("level") or 1)
        label, item = forge_relic(room, str(dungeon["name"]), level, idx)
        relics.setdefault(label, item)
        drops = list(boss.get("drops") or [])
        if label not in drops:
            drops.append(label)
        boss["drops"] = drops
    return relics
