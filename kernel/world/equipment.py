"""CARD: equipment -- equip gear into slots; its modifiers bend the derived stats.

A character wears gear in fixed slots (weapon, body, head, arm, two accessories). An item is
equippable when its seed data names a `slot` and the flat `mods` it grants. Equipping marks
the carried item as worn; its modifiers are gathered and fed through the ModifierStack into the
derived stats (ADR-0006 derived math + the salvaged stack). This card owns the mechanic and the
modifier math; the score sheet only projects the result.
"""

from __future__ import annotations

from kernel.shelf.stats import ModifierStack, Stat, StatModifier

# import the MODULES, not their globals: tests swap items.ITEMS / gearsets.SETS
from kernel.world import gearsets, items
from kernel.world.score_sheet_model import EquipmentLoadout
from kernel.world.session import Session, sentence_case

SLOTS = ("weapon", "body", "head", "arm", "leg", "feet", "accessory_1", "accessory_2")


def equip(session: Session, word: str) -> str:
    """Wear a carried, equippable item in its slot. Refuses loud on a bad item or slot."""
    iid = items.trace_item(word, items.carrier(session.player_id))
    if iid is None:
        return "You aren't carrying that."
    item = items.ITEMS[iid]
    slot = item["slot"]
    if not slot:
        return f"{sentence_case(item['name'])} is not something you can equip."
    if slot not in SLOTS:
        return f"{sentence_case(item['name'])} names an unknown slot '{slot}'."
    session.equipped[slot] = iid
    return f"You equip {item['name']} ({slot})."


def unequip(session: Session, slot: str) -> str:
    """Remove the gear in a slot. The item stays in your inventory."""
    slot = slot.strip().lower()
    if slot not in session.equipped:
        return f"Nothing is equipped in '{slot}'."
    item = items.ITEMS[session.equipped.pop(slot)]
    return f"You remove {item['name']} from {slot}."


def equipped_modifiers(session: Session) -> dict[str, list[StatModifier]]:
    """Gather every equipped item's modifiers, grouped by the stat they target, PLUS any set bonus
    earned by wearing a whole gear set at once (kernel.world.gearsets). Set bonuses stack on top of
    the pieces' own mods, so a full regional set beats three unrelated pieces of the same tier."""
    from kernel.world import durability  # noqa: PLC0415

    by_target: dict[str, list[StatModifier]] = {}
    worn_prototypes: set[str] = set()
    for slot, iid in session.equipped.items():
        if durability.is_broken(iid):
            continue  # a broken piece grants nothing (and no set bonus) until it is repaired
        worn_prototypes.add(items.prototype_of(iid))
        for target, amount in items.ITEMS[iid]["mods"].items():
            by_target.setdefault(target, []).append(StatModifier(source=slot, flat=amount))
    for target, amount in gearsets.active_set_bonuses(worn_prototypes).items():
        by_target.setdefault(target, []).append(StatModifier(source="set-bonus", flat=amount))
    return by_target


def item_power(iid: str) -> int:
    """One item's power: the sum of the stat modifiers it grants. A single number to rank gear by.
    A raid drop, its affixes rolled by a level-300 foe, carries far bigger mods than an open-world
    piece, so this simply reads the gear treadmill the affix roll already scales -- no stored ilvl,
    derive-don't-store: the mods are canonical, the power recomputes."""
    return sum(items.ITEMS[iid]["mods"].values())


def gear_score(session: Session) -> int:
    """A hero's GEAR SCORE: the summed power of everything worn, INCLUDING the set bonuses a full
    gear set grants (equipped_modifiers composes both). The endgame progression metric -- an
    ungeared hero reads 0; push it up by trading open-world pieces for raid gear and full sets."""
    return sum(mod.flat for stack in equipped_modifiers(session).values() for mod in stack)


def apply_stat_modifiers(
    base_derived: dict[str, int], mods_by_target: dict[str, list[StatModifier]]
) -> dict[str, int]:
    """Fold a target->modifiers map into derived stats via the ModifierStack (pure). Reused by
    equipment and by job perks, so both bend the stats the same, order-independent way."""
    if not mods_by_target:
        return dict(base_derived)
    result = dict(base_derived)
    for stat, value in base_derived.items():
        if stat in mods_by_target:
            # Clamp the incoming derived value into the Stat's own [0, 9999] bounds first:
            # derived_stats documents that it can return a negative/oversized value on hostile
            # attributes, and this next pipeline stage must clamp it, not raise on the Stat bound.
            bounded = Stat(name=stat, base=max(0, min(value, 9999)), min_value=0, max_value=9999)
            result[stat] = ModifierStack(tuple(mods_by_target[stat])).apply(bounded)
    return result


def apply_equipment(base_derived: dict[str, int], session: Session) -> dict[str, int]:
    """Return derived stats with equipped gear folded in via the ModifierStack (pure)."""
    return apply_stat_modifiers(base_derived, equipped_modifiers(session))


def equipped_loadout(session: Session) -> EquipmentLoadout:
    """The sheet view of what is worn: each slot's item name (blank when empty)."""
    names = {slot: items.ITEMS[iid]["name"] for slot, iid in session.equipped.items()}
    return EquipmentLoadout(
        weapon=names.get("weapon", ""),
        body=names.get("body", ""),
        head=names.get("head", ""),
        arm=names.get("arm", ""),
        leg=names.get("leg", ""),
        feet=names.get("feet", ""),
        accessory_1=names.get("accessory_1", ""),
        accessory_2=names.get("accessory_2", ""),
    )
