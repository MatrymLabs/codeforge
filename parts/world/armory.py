"""CARD: armory -- a procedural gear factory: slot x element-flavour x level -> equippable loot.

The world-generation lever (rooms via wildlands/spiral, creatures via bestiary, rarity via affixes)
pointed at GEAR. A million-room world full of named guardians is only worth hunting if felling one
can drop something to wear; hand-authoring a weapon for every level band and biome is the same
repetitive filler the bestiary retired for creatures. So this forges a base equippable from a
small, inspectable schema:

    equip SLOT (weapon/body/head/arm/accessory) x element FLAVOUR (ember/frost/storm/...) x LEVEL

`forge_gear` returns one base prototype (name, slot, level-scaled mods); `arm_guardians` gives every
generated GUARDIAN a themed gear drop and returns the prototypes to merge into the item table. The
base is only the floor: on defeat, a levelled foe's equippable drop runs the affix factory
(parts.shelf.affixes), which rolls a rarity + named affixes on top, so one forged blade falls as a
whole spread of gear ("a Cruel ember-forged warblade of the Bear [rare]").

Deterministic and pure (no randomness at generation; the affix roll is the only chance, at drop
time), so the same guardian always carries the same base gear -- reproducible like the rest of the
generators.
"""

from __future__ import annotations

from parts.world.seed import Item, Npc

# An element (a RESIST code the foe strikes with) marks its forged gear with a flavour word.
_FLAVOUR: dict[str, str] = {
    "FIR": "ember",
    "ICE": "frost",
    "LGT": "storm",
    "WND": "gale",
    "ERT": "stone",
    "WTR": "tide",
    "HLY": "hallowed",
    "DRK": "shadow",
    "PSN": "venom",
    "CRS": "cursed",
}

# Each equip slot: the nouns its gear can be, the derived stat its base mod raises, and how heavily
# (weapon leans ATK, armour DEF, trinkets ACC/EVA). The affix factory scales and embellishes on top.
_SLOTS: tuple[tuple[str, tuple[str, ...], str, float], ...] = (
    ("weapon", ("warblade", "cleaver", "spear"), "ATK", 1.0),
    ("body", ("plate", "hauberk", "cuirass"), "DEF", 1.0),
    ("head", ("helm", "crown", "hood"), "DEF", 0.6),
    ("arm", ("bracers", "gauntlets", "vambrace"), "DEF", 0.5),
    ("accessory_1", ("band", "ring", "torc"), "ACC", 0.7),
    ("accessory_2", ("charm", "talisman", "sigil"), "EVA", 0.7),
)


def forge_gear(level: int, element: str, idx: int) -> tuple[str, Item]:
    """Forge one base equippable for a level and element, its slot and noun chosen by index. Returns
    (prototype-label, item); the label folds flavour + noun + level so identical gear dedupes into
    one shared prototype. Deterministic by (level, element, idx)."""
    slot, nouns, target, weight = _SLOTS[idx % len(_SLOTS)]
    noun = nouns[(idx // len(_SLOTS)) % len(nouns)]
    flavour = _FLAVOUR.get(element, "worn")
    article = "an" if flavour[0] in "aeiou" else "a"
    amount = max(1, int((2 + level // 6) * weight))  # a modest floor; affixes add the rest
    label = f"gear_{flavour}_{noun}_l{level}"
    item = Item(
        name=f"{article} {flavour}-forged {noun}",
        keywords=[flavour, noun, "gear"],
        location="nowhere",  # a drop-only prototype: it exists to be cloned onto the floor
        slot=slot,
        mods={target: amount},
    )
    return label, item


def arm_guardians(npcs: dict[str, Npc]) -> dict[str, Item]:
    """Give every generated GUARDIAN a themed gear drop; return the gear prototypes to merge into
    the item table. A guardian is a non-ambient, levelled foe with no drop yet; ambient wildlife and
    foes that already drop something are left untouched. Mutates each armed foe's `drops` in place;
    the returned prototypes must be merged into ITEMS before the boot link-audit runs."""
    gear: dict[str, Item] = {}
    for idx, npc in enumerate(npcs.values()):
        if npc.get("ambient") or npc.get("hp", 0) <= 0 or npc.get("drops"):
            continue
        level = npc.get("level", 0)
        if not level:
            continue
        label, item = forge_gear(level, str(npc.get("attack_element", "")), idx)
        gear.setdefault(label, item)  # identical gear shares one prototype
        npc["drops"] = [label]
    return gear
