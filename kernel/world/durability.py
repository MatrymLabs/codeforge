"""CARD: durability -- gear wears with use and breaks; repair is the economy's coin sink (game).

The economy had faucets (kill coin, loot, bounties) and no drain, so purses only ever grow. This is
the sink the gap analysis named: every equipped piece has DURABILITY that erodes as you fight -- a
weapon dulls as it strikes, armour dents as it is struck -- and at zero it is BROKEN and grants none
of its stat mods until mended. Repair costs coins, so the more you fight the more you spend to keep
fighting, and the coin faucet finally has somewhere to drain.

Durability lives on the item instance (`items.ITEMS[iid]['durability']`); a gear piece with no field
reads full, so a fresh drop needs no init and old saves upgrade cleanly. It persists on the one
snapshot both worn gear and the bag ride (characters.snapshot_item), so wear survives logout and you
cannot repair by relogging. Non-gear items (no slot) never wear -- a potion has no durability.
"""

from __future__ import annotations

from kernel.world import items
from kernel.world.coinage import purse
from kernel.world.session import Session

MAX = 100  # a fresh gear piece's full durability
REPAIR_COST_PER_POINT = 1  # coins to restore one point of wear -- the sink's rate


def current(iid: str) -> int:
    """A gear piece's current durability (full when it has never worn, or the item is unknown)."""
    item = items.ITEMS.get(iid)
    return MAX if item is None else int(item.get("durability", MAX))


def is_gear(iid: str) -> bool:
    """True if the item is equippable (only gear tracks durability -- a potion does not wear)."""
    item = items.ITEMS.get(iid)
    return bool(item and item.get("slot"))


def is_broken(iid: str) -> bool:
    """True once a gear piece has worn to zero: it grants no stat mods until repaired."""
    return is_gear(iid) and current(iid) <= 0


def wear(iid: str, amount: int = 1) -> None:
    """Wear a gear piece by `amount`, floored at zero. A non-gear item (no slot) never wears, so
    combat can call this on any equipped id without checking."""
    if not is_gear(iid) or amount <= 0:
        return
    items.ITEMS[iid]["durability"] = max(0, current(iid) - amount)


def repair(iid: str) -> int:
    """Restore one gear piece to full; return the points restored (0 if already full / not gear)."""
    if not is_gear(iid):
        return 0
    restored = MAX - current(iid)
    if restored > 0:
        items.ITEMS[iid]["durability"] = MAX
    return restored


def repair_cost(session: Session) -> int:
    """The coins to fully repair everything the hero has equipped (0 when all is in good repair)."""
    return sum(MAX - current(iid) for iid in session.equipped.values()) * REPAIR_COST_PER_POINT


def repair_session(session: Session) -> str:
    """`repair`: mend all worn gear for coins -- the economy's sink. Refuses loud (and charges
    nothing) when the purse is short or there is nothing to mend."""
    cost = repair_cost(session)
    if cost <= 0:
        return "Your gear is whole; there is nothing to mend."
    if session.coins < cost:
        return f"Repairs would cost {purse(cost)}; you carry only {purse(session.coins)}."
    session.coins -= cost
    for iid in list(session.equipped.values()):
        repair(iid)
    return f"You mend your gear for {purse(cost)}. (purse: {purse(session.coins)})"
