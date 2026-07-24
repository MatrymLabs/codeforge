"""CARD: consumables -- quaff a carried item for a one-shot restore (potions and their kin).

A consumable declares a `consume` effect in the seed ({hp: 30} / {mp: 10} / both). `quaff <item>`
finds it in the player's inventory, restores those pools (clamped to their maxima), and spends the
item (a single use -- it leaves your hands). This is the item CATEGORY the game lacked: gear you
equip, and now supplies you spend. Distinct from `use <ability>` (a job move), on purpose.

Inputs: a Session (its inventory + resources) and the player's word. Output: the line they see.
Refuses loud and early: nothing named that, or a thing that is not drinkable.
"""

from __future__ import annotations

from parts.world import items
from parts.world.session import Session, sentence_case


def quaff(session: Session, word: str) -> str:
    """`quaff <item>`: spend a carried consumable and restore its pools. Fails loud on a miss."""
    if not word.strip():
        return "Quaff what? You must be carrying it."
    iid = items.trace_item(word.strip().lower(), "player")
    if iid is None:
        return "You aren't carrying that."
    item = items.ITEMS[iid]
    effect = item.get("consume")
    if not effect:
        return f"{sentence_case(item['name'])} is not something you can drink."
    restored = []
    for pool in ("hp", "mp"):
        amount = effect.get(pool, 0)
        if amount and pool in session.resources:
            before = session.resources[pool]
            session.resources[pool] = before.heal(amount)
            gained = session.resources[pool].current - before.current
            restored.append(f"{gained} {pool.upper()}")
    name = item["name"]
    del items.ITEMS[iid]  # a consumable is spent: it leaves your hands (a within-session effect)
    gains = " and ".join(restored) if restored else "nothing (already full)"
    return f"You quaff {name} and recover {gains}."
