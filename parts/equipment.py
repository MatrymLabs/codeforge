"""CARD: equipment -- equip gear into slots; its modifiers bend the derived stats.

A character wears gear in fixed slots (weapon, body, head, arm, two accessories). An item is
equippable when its seed data names a `slot` and the flat `mods` it grants. Equipping marks
the carried item as worn; its modifiers are gathered and fed through the ModifierStack into the
derived stats (ADR-0006 derived math + the salvaged stack). This card owns the mechanic and the
modifier math; the score sheet only projects the result.
"""

from __future__ import annotations

from parts import items  # import the MODULE, not its globals: tests swap items.ITEMS
from parts.score_sheet import EquipmentLoadout
from parts.session import Session
from parts.stats import ModifierStack, Stat, StatModifier

SLOTS = ("weapon", "body", "head", "arm", "accessory_1", "accessory_2")


def equip(session: Session, word: str) -> str:
    """Wear a carried, equippable item in its slot. Refuses loud on a bad item or slot."""
    iid = items.trace_item(word, "player")
    if iid is None:
        return "You aren't carrying that."
    item = items.ITEMS[iid]
    slot = item["slot"]
    if not slot:
        return f"{item['name'].capitalize()} is not something you can equip."
    if slot not in SLOTS:
        return f"{item['name'].capitalize()} names an unknown slot '{slot}'."
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
    """Gather every equipped item's modifiers, grouped by the stat they target."""
    by_target: dict[str, list[StatModifier]] = {}
    for slot, iid in session.equipped.items():
        for target, amount in items.ITEMS[iid]["mods"].items():
            by_target.setdefault(target, []).append(StatModifier(source=slot, flat=amount))
    return by_target


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
            bounded = Stat(name=stat, base=value, min_value=0, max_value=9999)
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
        accessory_1=names.get("accessory_1", ""),
        accessory_2=names.get("accessory_2", ""),
    )
