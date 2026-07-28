"""CARD: reputation -- a hero's numeric STANDING with each Order, over the factions (`standing`).

The Orders (parts.world.orders) are a sworn allegiance; the factions card (parts.world.factions)
gave them a relationship to each other (allied / rival). What neither carried was how a single hero
STANDS with each Order over time -- a numeric reputation that content can raise, spend, and gate on.
This is that substrate: a per-character standing per Order, earned through deeds, banded into named
tiers (Hostile .. Revered), and persisted (derive-don't-store holds -- the tier recomputes from the
stored number).

It composes WITH the faction politics: a deed that pleases one Order pleases its allies a little and
offends its rivals a little (the spillover reads relations from factions.relations_of). `grant` is
the single earn/lose door content calls; swearing an Order grants a starting standing; the
`standing` verb shows a hero where they sit. Faction-gated content + the faction story pull on this.
"""

from __future__ import annotations

from parts.world.factions import relations_of
from parts.world.orders import ORDERS, order_name
from parts.world.session import Session

#: Named standing tiers by minimum reputation, highest first. Below the lowest floor reads Hostile.
#: Deliberately simple and legible -- every 100 of standing is roughly a tier, so a hero feels the
#: climb. The tier is DERIVED from the stored number, never persisted.
_TIERS: tuple[tuple[int, str], ...] = (
    (600, "Revered"),
    (300, "Honored"),
    (100, "Friendly"),
    (0, "Neutral"),
    (-100, "Unfriendly"),
)
_HOSTILE = "Hostile"  # below the lowest tier floor

#: The standing a hero gains with an Order the moment they swear to it (they start Friendly).
SWEAR_STANDING = 100


def tier_for(standing: int) -> str:
    """The named tier a standing value falls in (Revered .. Hostile). Derived, never stored."""
    for floor, name in _TIERS:
        if standing >= floor:
            return name
    return _HOSTILE


def standing_of(session: Session, order: str) -> int:
    """A hero's current standing with an Order (0 for one they have no history with)."""
    return session.reputation.get(order, 0)


def grant(session: Session, order: str, amount: int) -> str | None:
    """Raise (or lower, if `amount` is negative) a hero's standing with an Order -- the single earn
    door content calls. The deed spills over the faction politics: the Order's ALLIES shift a little
    the same way, its RIVALS the opposite (half the amount each), so reputation is a web, not a set
    of independent bars. Returns a line for each Order whose TIER changed, or None if none did.
    An unknown Order is a clean no-op."""
    if order not in ORDERS:
        return None
    allies, rivals = relations_of(order)
    changes: dict[str, int] = {order: amount}
    for ally in allies:
        changes[ally] = changes.get(ally, 0) + amount // 2
    for rival in rivals:
        changes[rival] = changes.get(rival, 0) - amount // 2
    lines: list[str] = []
    for oid, delta in changes.items():
        if delta == 0:
            continue
        before = tier_for(session.reputation.get(oid, 0))
        session.reputation[oid] = session.reputation.get(oid, 0) + delta
        after = tier_for(session.reputation[oid])
        if after != before:
            lines.append(f"You are now {after} with {order_name(oid)}.")
    return "\n".join(lines) or None


def render_standing(session: Session) -> str:
    """`standing` -- the hero's reputation with every Order, its tier and value, their own Order
    marked. A menu of where they stand and where the work remains."""
    lines = ["Your standing with the Orders:"]
    for oid, order in ORDERS.items():
        rep = session.reputation.get(oid, 0)
        mark = " (sworn)" if session.order == oid else ""
        lines.append(f"  {order['name']}{mark}: {tier_for(rep)} ({rep})")
    return "\n".join(lines)


def serialize(session: Session) -> str:
    """A hero's standings as a compact persisted string: 'order:standing' pairs, comma-joined. Empty
    when the hero has no standing anywhere (a fresh hero saves none)."""
    pairs = [f"{oid}:{rep}" for oid, rep in sorted(session.reputation.items()) if rep != 0]
    return ",".join(pairs)


def restore(session: Session, blob: str) -> None:
    """Rebuild standings from `serialize`'s string. Unknown Orders or malformed pairs are dropped
    (an Order a later seed removed must not crash an old save) -- forgiving restore."""
    session.reputation = {}
    for pair in blob.split(","):
        oid, _, value = pair.partition(":")
        if oid in ORDERS and _is_int(value):
            session.reputation[oid] = int(value)


def _is_int(text: str) -> bool:
    """True if `text` is a base-10 integer, including a leading '-' (isdigit rejects negatives)."""
    return text.lstrip("-").isdigit() and text not in ("", "-")
