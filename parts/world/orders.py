"""CARD: orders -- the Orders a Forger may swear to (a persisted guild-allegiance).

An Order is a chosen guild-allegiance: the same shape of persisted identity fact as a rank, one
lowercase label on the character record, sworn or changed at the Orders' Row (world bible s.25).
This card owns the roster and the join gate; a named hero swears an Order and it survives logout.
Perks the Orders grant fold into the sheet separately -- this slice is the allegiance primitive.

Inputs: a Session and the raw argument of a `join` command. Output: the line the player sees.
Only a NAMED hero may swear (an Order must persist, so there must be a record to persist onto).
"""

from __future__ import annotations

from parts.shelf.stats import StatModifier
from parts.world.session import Session, display_name

# Each Order grants a small, permanent combat perk: flat modifiers on the derived stats, folded into
# the sheet and into combat through the same ModifierStack as equipment and job perks. Warcraft and
# Making bend the wired stats (ATK/DEF) directly; Knowing also readies MAG DEF for future magic.
ORDER_PERKS: dict[str, dict[str, int]] = {
    "making": {"DEF": 4},  # the smiths: a bulwark
    "gathering": {"ATK": 2, "DEF": 2},  # the finders: a balanced skirmisher
    "warcraft": {"ATK": 4},  # the soldiers: the edge
    "knowing": {"DEF": 3, "MAG DEF": 3},  # the scholars: warded now, and against magic to come
}

# The four Orders of the Kindlands (world bible s.25). Labels are lowercase_snake_case and FROZEN
# (they persist on the character record); the display name and creed are free to change.
ORDERS: dict[str, dict[str, str]] = {
    "making": {
        "name": "the Making Order",
        "creed": "We forge. What was unmade, we make again.",
    },
    "gathering": {
        "name": "the Gathering Order",
        "creed": "We find. The Anvil's every ember has a keeper.",
    },
    "warcraft": {
        "name": "the Warcraft Order",
        "creed": "We hold the line. The Spiral does not fall while we stand.",
    },
    "knowing": {
        "name": "the Knowing Order",
        "creed": "We remember. A world forgotten is a world unmade twice.",
    },
}


def order_name(label: str) -> str:
    """The display name of an Order label, or '' for none/unknown."""
    order = ORDERS.get(label)
    return order["name"] if order else ""


def order_modifiers(order_label: str) -> dict[str, list[StatModifier]]:
    """The sworn Order's perk as stat modifiers, grouped by target (empty for none/unknown).

    Same shape as equipment and job perks, so combat and the sheet fold it through the one stack."""
    perks = ORDER_PERKS.get(order_label, {})
    name = order_name(order_label) or order_label
    return {stat: [StatModifier(source=name, flat=amount)] for stat, amount in perks.items()}


def _roster() -> str:
    """The Orders on offer, one per line, for the bare `join` command."""
    lines = [f"  {label} -- {order['name']}: {order['creed']}" for label, order in ORDERS.items()]
    return "The Orders of the Row:\n" + "\n".join(lines) + "\nSwear with: join <order>"


def swear_order(session: Session, arg: str) -> str:
    """`join <order>`: swear a named hero to an Order (persisted), or list the Orders when bare.

    Refuses loud and early: an unnamed session has no record to persist onto, and an unknown
    Order name is rejected with the roster rather than silently ignored."""
    choice = arg.strip().lower()
    if not choice:
        current = order_name(session.order)
        standing = f"You are sworn to {current}.\n" if current else ""
        return standing + _roster()
    if not session.named:
        return "Only a named Forger can swear to an Order. Make yourself known first."
    if choice not in ORDERS:
        return f"There is no Order called '{arg.strip()}' on the Row.\n" + _roster()
    if session.order == choice:
        return f"You are already sworn to {order_name(choice)}."
    session.order = choice
    from parts.world.characters import save_character

    save_character(session)
    from parts.world.events import announce

    announce(
        session.location,
        f"{display_name(session.player_id)} swears to {order_name(choice)}.",
        exclude=session.player_id,
    )
    return f'You swear to {order_name(choice)}. "{ORDERS[choice]["creed"]}"'
