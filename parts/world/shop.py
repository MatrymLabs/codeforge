"""CARD: shop -- buy and sell at a merchant's stall (the coin economy's spending end).

A merchant NPC declares a `shop` in the seed (sells/buys price tables; the world stays data). This
card is the till: `render_shop` lists the wares, `buy` spends coins for a fresh instance of a sold
prototype, `sell` pays coins for a carried item the shop buys. All three find the shopkeeper in the
player's current room, so a stall only trades where it stands.

Inputs: a Session (carrying the purse + inventory) and the player's word. Output: the line they see.
Refuses loud and early: no shop here, an item not for sale, an empty purse, a thing you don't carry.
"""

from __future__ import annotations

from parts.world import items
from parts.world.npcs import NPCS, npcs_in
from parts.world.session import Session, sentence_case


def _shopkeeper(room_id: str) -> str | None:
    """The id of a merchant NPC in this room (the first that keeps a shop), or None."""
    for nid in npcs_in(room_id):
        if NPCS[nid].get("shop"):
            return nid
    return None


def render_shop(session: Session) -> str:
    """List a present merchant's wares and what it buys, with the player's purse. `shop` verb."""
    nid = _shopkeeper(session.location)
    if nid is None:
        return "There is no one selling anything here."
    npc = NPCS[nid]
    shop = npc["shop"]
    lines = [f"{sentence_case(npc['name'])}'s wares (your purse: {session.coins} coins):"]
    sells = shop.get("sells", {})
    if sells:
        lines.append("  For sale (buy <item>):")
        for proto, price in sells.items():
            lines.append(f"    {items.PROTOTYPES[proto]['name']} -- {price} coins")
    buys = shop.get("buys", {})
    if buys:
        lines.append("  Buying (sell <item>):")
        for proto, price in buys.items():
            lines.append(f"    {items.PROTOTYPES[proto]['name']} -- {price} coins")
    return "\n".join(lines)


def _match_sold(word: str, sells: dict[str, int]) -> str | None:
    """The prototype the player's word names among a shop's wares, matched on item keywords."""
    for proto in sells:
        if word in items.PROTOTYPES[proto]["keywords"] or word == proto:
            return proto
    return None


def buy(session: Session, word: str) -> str:
    """Spend coins for a sold item; a fresh instance is cloned into your inventory."""
    if not word.strip():
        return "Buy what? Try SHOP to see the wares."
    nid = _shopkeeper(session.location)
    if nid is None:
        return "There is no one selling anything here."
    sells = NPCS[nid]["shop"].get("sells", {})
    proto = _match_sold(word.strip().lower(), sells)
    if proto is None:
        return "That is not for sale here. Try SHOP to see the wares."
    price = sells[proto]
    if session.coins < price:
        return f"You cannot afford that ({price} coins; your purse holds {session.coins})."
    session.coins -= price
    items.clone(proto, "player")
    _save(session)
    name = items.PROTOTYPES[proto]["name"]
    return f"You buy {name} for {price} coins. (purse: {session.coins})"


def sell(session: Session, word: str) -> str:
    """Sell a carried item the shop buys, for coins."""
    if not word.strip():
        return "Sell what? You must be carrying it."
    nid = _shopkeeper(session.location)
    if nid is None:
        return "There is no one buying anything here."
    buys = NPCS[nid]["shop"].get("buys", {})
    iid = items.trace_item(word.strip().lower(), "player")
    if iid is None:
        return "You aren't carrying that."
    proto = items.prototype_of(iid)
    if proto not in buys:
        return f"{sentence_case(items.ITEMS[iid]['name'])} is not something this shop buys."
    price = buys[proto]
    name = items.ITEMS[iid]["name"]
    del items.ITEMS[iid]  # the shop takes the item off your hands
    for slot, worn in list(session.equipped.items()):
        if worn == iid:
            del session.equipped[slot]  # sold from a slot: unequip it too
    session.coins += price
    _save(session)
    return f"You sell {name} for {price} coins. (purse: {session.coins})"


def _save(session: Session) -> None:
    """Persist the purse (and inventory-derived state) after a trade, for a named hero."""
    if session.named:
        from parts.world.characters import save_character

        save_character(session)
