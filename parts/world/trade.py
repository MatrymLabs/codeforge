"""CARD: trade -- a safe, atomic swap of goods and coin between two co-located heroes.

The first player-to-player economy loop: two heroes in the same room each stake an offer (items from
their hands, coin from their purse), both confirm, and the swap happens all at once or not at all.
The whole point is atomicity: goods and coin are validated on both sides and then moved in one step,
so a trade can never duplicate an item, lose one, or pay coin a hero no longer has. Any change to an
offer un-confirms both sides, so no one can confirm a deal and then quietly alter it.

Transient by design, like the party: all state lives in this module's registry keyed by player id
(`_TRADES`, `_OFFERS`... never persisted), so a trade dissolves on cancel or logout with nothing to
unwind, because nothing moves until the atomic execute. Reads live session presence + purse (coins)
and moves items by reassigning their carrier tag (per-player inventory), through the same item logic
a `take` uses; it mutates no world state of its own beyond the swap it is asked to make.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parts.world.events import announce_to
from parts.world.items import ITEMS, carrier, items_in, trace_item
from parts.world.session import SESSIONS, display_name


@dataclass
class Offer:
    """One hero's side of a trade: the item ids staked, the coin staked, and whether they have
    locked it in. Confirming both sides fires the swap."""

    items: list[str] = field(default_factory=list)
    coins: int = 0
    confirmed: bool = False


@dataclass
class Trade:
    """An open trade between two heroes. Both parties map to the SAME Trade in the registry, so
    either can read and drive it. `offers` holds each side by player id."""

    a: str
    b: str
    offers: dict[str, Offer] = field(default_factory=dict)

    def other(self, player_id: str) -> str:
        return self.b if player_id == self.a else self.a


# All trade state, owned here. `_TRADES` maps each of the two parties to their shared Trade;
# `_INVITES` maps an invited hero to the id of the hero who proposed to them.
_TRADES: dict[str, Trade] = {}
_INVITES: dict[str, str] = {}


def _present_together(a: str, b: str) -> bool:
    """Both heroes online and in the same room (a trade is face to face)."""
    sa, sb = SESSIONS.get(a), SESSIONS.get(b)
    return sa is not None and sb is not None and sa.location == sb.location


def _unconfirm(trade: Trade) -> None:
    """Any change to an offer voids both confirmations, so a locked deal can never be altered."""
    for offer in trade.offers.values():
        offer.confirmed = False


def propose(actor: str, target_name: str) -> str:
    """Offer to trade with a co-located hero. Fails loud on a self-trade, an absent or distant
    target, or either party already being in a trade."""
    target = target_name.strip().lower()
    if not target:
        return "Trade with whom? (trade <player>)"
    if target == actor:
        return "You cannot trade with yourself."
    if actor in _TRADES:
        return "You are already in a trade; finish or cancel it first."
    if target in _TRADES:
        return f"{display_name(target)} is already in a trade."
    if not _present_together(actor, target):
        return f"{display_name(target)} is not here to trade with."
    _INVITES[target] = actor
    announce_to([target], f"\n{display_name(actor)} offers to trade. (trade accept)")
    return f"You offer to trade with {display_name(target)}."


def accept(actor: str) -> str:
    """Accept a pending trade offer, opening the trade window for both heroes."""
    proposer = _INVITES.get(actor)
    if proposer is None:
        return "No one has offered to trade with you."
    if actor in _TRADES or proposer in _TRADES:
        _INVITES.pop(actor, None)
        return "That trade is no longer available."
    if not _present_together(actor, proposer):
        _INVITES.pop(actor, None)
        return f"{display_name(proposer)} is no longer here."
    trade = Trade(a=proposer, b=actor, offers={proposer: Offer(), actor: Offer()})
    _TRADES[proposer] = _TRADES[actor] = trade
    _INVITES.pop(actor, None)
    announce_to(
        [proposer], f"\n{display_name(actor)} accepts. The trade is open. (trade add <item>)"
    )
    return f"You open a trade with {display_name(proposer)}. (trade add <item>, trade coins <n>)"


def add_item(actor: str, word: str) -> str:
    """Stake a carried item on your side of the trade. Un-confirms both sides."""
    trade = _TRADES.get(actor)
    if trade is None:
        return "You are not in a trade. (trade <player> to start one)"
    thing = word.strip().lower()
    if not thing:
        return "Add what? (trade add <item>)"
    iid = trace_item(thing, carrier(actor))
    if iid is None:
        return "You aren't carrying that."
    offer = trade.offers[actor]
    if iid in offer.items:
        return f"{ITEMS[iid]['name']} is already in your offer."
    offer.items.append(iid)
    _unconfirm(trade)
    announce_to([trade.other(actor)], f"\n{display_name(actor)} adds {ITEMS[iid]['name']}.")
    return f"You add {ITEMS[iid]['name']} to the trade."


def offer_coins(actor: str, amount_word: str) -> str:
    """Stake coin from your purse on your side. Un-confirms both sides."""
    trade = _TRADES.get(actor)
    if trade is None:
        return "You are not in a trade."
    try:
        amount = int(amount_word.strip())
    except ValueError:
        return "Offer how many coins? (trade coins <number>)"
    if amount < 0:
        return "You cannot offer a negative sum."
    session = SESSIONS.get(actor)
    if session is None or amount > session.coins:
        return "You do not have that many coins."
    trade.offers[actor].coins = amount
    _unconfirm(trade)
    announce_to([trade.other(actor)], f"\n{display_name(actor)} offers {amount} coins.")
    return f"You offer {amount} coins."


def confirm(actor: str) -> str:
    """Lock in your side. When BOTH heroes have confirmed, the swap executes atomically."""
    trade = _TRADES.get(actor)
    if trade is None:
        return "You are not in a trade."
    trade.offers[actor].confirmed = True
    other = trade.other(actor)
    if trade.offers[other].confirmed:
        return _execute(trade)
    announce_to([other], f"\n{display_name(actor)} confirms the trade. (trade confirm to seal it)")
    return "You confirm your side. Waiting for the other to confirm."


def cancel(actor: str) -> str:
    """Abort the trade (or decline a pending offer). Nothing has moved, so nothing to undo."""
    trade = _TRADES.get(actor)
    if trade is None:
        if _INVITES.pop(actor, None) is not None:
            return "You decline the trade offer."
        return "You are not in a trade."
    other = trade.other(actor)
    _TRADES.pop(actor, None)
    _TRADES.pop(other, None)
    announce_to([other], f"\n{display_name(actor)} cancels the trade.")
    return "You cancel the trade."


def _execute(trade: Trade) -> str:
    """Both sides confirmed: validate every staked item and coin on BOTH sides, then move them all
    in one step. Validate-all-then-apply is the atomicity guarantee: if anything is missing (an item
    dropped, coin spent, a hero stepped away) the whole trade aborts and nothing changes hands."""
    a, b = trade.a, trade.b
    if not _present_together(a, b):
        return _abort(trade, "The trade fails: someone stepped away.")
    for owner_id in (a, b):
        offer = trade.offers[owner_id]
        held = set(items_in(carrier(owner_id)))
        if any(iid not in held for iid in offer.items):
            return _abort(trade, "The trade fails: an offered item is no longer in hand.")
        session = SESSIONS[owner_id]
        if offer.coins > session.coins:
            return _abort(trade, "The trade fails: the coin is no longer there.")
    # Everything validated. Apply the swap in one pass; no partial state is possible now.
    for giver, receiver in ((a, b), (b, a)):
        offer = trade.offers[giver]
        for iid in offer.items:
            ITEMS[iid]["location"] = carrier(receiver)
        SESSIONS[giver].coins -= offer.coins
        SESSIONS[receiver].coins += offer.coins
    _TRADES.pop(a, None)
    _TRADES.pop(b, None)
    announce_to([a, b], "\nThe trade is sealed. The goods change hands.")
    return "The trade is sealed. The goods change hands."


def _abort(trade: Trade, reason: str) -> str:
    _TRADES.pop(trade.a, None)
    _TRADES.pop(trade.b, None)
    announce_to([trade.a, trade.b], f"\n{reason}")
    return reason


def render(actor: str) -> str:
    """Show the open trade: both sides, their stakes, and who has confirmed."""
    trade = _TRADES.get(actor)
    if trade is None:
        return "You are not in a trade. (trade <player> to start one)"
    lines = [f"Trade with {display_name(trade.other(actor))}:"]
    for who in (actor, trade.other(actor)):
        offer = trade.offers[who]
        mark = " [confirmed]" if offer.confirmed else ""
        label = "You" if who == actor else display_name(who)
        goods = ", ".join(ITEMS[iid]["name"] for iid in offer.items) or "nothing"
        coin = f" + {offer.coins} coins" if offer.coins else ""
        lines.append(f"  {label}: {goods}{coin}{mark}")
    lines.append("(trade add <item>, trade coins <n>, trade confirm, trade cancel)")
    return "\n".join(lines)


def on_disconnect(player_id: str) -> None:
    """Logout cleanup: cancel any open trade or pending offer for the departing hero. Nothing has
    moved (items swap only on the atomic execute), so cancelling leaves purses and bags intact."""
    if player_id in _TRADES:
        cancel(player_id)
    _INVITES.pop(player_id, None)
    for target, proposer in list(_INVITES.items()):
        if proposer == player_id:
            _INVITES.pop(target, None)


def _reset() -> None:
    """Clear all trade state. For tests only, so one test's trades never leak into the next."""
    _TRADES.clear()
    _INVITES.clear()
