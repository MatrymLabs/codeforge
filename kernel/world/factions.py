"""CARD: factions -- the standing between the Orders: who is allied, who is rival (the conflicts).

The Orders (kernel.world.orders) already exist -- a Forger swears to one, a persisted allegiance.
What they lacked was a relationship to EACH OTHER: the faction conflicts the campaign (Part II) asks
every zone and story to reckon with. This adds exactly that, as a model over the existing Orders (it
never replaces them): each pair of Orders stands ALLIED, RIVAL, or NEUTRAL; `stance`/`render` read.

It is the seam the world-simulation layer pulls next -- a faction-gated spawn or a faction storyline
asks `stance(mine, theirs)` -- and, today, the `factions` verb shows a sworn hero where they stand.
Pure data over the Orders; no new allegiance, no second source of truth -- the politics of the Row.
"""

from __future__ import annotations

from kernel.world.orders import ORDERS, order_name

# The politics of the Row, as unordered pairs. The four Orders fall into two axes: the hand that
# builds (Making + Gathering) against the memory and shield that endure (Warcraft + Knowing) is the
# alliance; the cross-cutting tensions (the new vs the old, the free wilds vs the held line) are the
# rivalries. Every pairing not named here is NEUTRAL.
_ALLIED: frozenset[frozenset[str]] = frozenset(
    {frozenset({"making", "gathering"}), frozenset({"warcraft", "knowing"})}
)
_RIVAL: frozenset[frozenset[str]] = frozenset(
    {frozenset({"making", "knowing"}), frozenset({"gathering", "warcraft"})}
)


def stance(order_a: str, order_b: str) -> str:
    """How two Orders stand: 'self' (the same Order), 'allied', 'rival', or 'neutral'. Symmetric;
    an unknown Order reads 'neutral' against all."""
    if order_a not in ORDERS or order_b not in ORDERS:
        return "neutral"
    if order_a == order_b:
        return "self"
    pair = frozenset({order_a, order_b})
    if pair in _ALLIED:
        return "allied"
    if pair in _RIVAL:
        return "rival"
    return "neutral"


def relations_of(order: str) -> tuple[list[str], list[str]]:
    """An Order's (allies, rivals) as label lists, each sorted. Empty for an unknown Order."""
    if order not in ORDERS:
        return [], []
    allies = sorted(o for o in ORDERS if stance(order, o) == "allied")
    rivals = sorted(o for o in ORDERS if stance(order, o) == "rival")
    return allies, rivals


def render_factions(sworn: str = "") -> str:
    """The politics of the Row: every Order with its allies and rivals. When `sworn` names the
    reader's own Order, its line is marked, so a hero sees where they stand."""
    lines = ["The politics of the Row:"]
    for label, order in ORDERS.items():
        allies, rivals = relations_of(label)
        ally_txt = ", ".join(order_name(a) for a in allies) or "none"
        rival_txt = ", ".join(order_name(r) for r in rivals) or "none"
        mark = " (yours)" if label == sworn else ""
        lines.append(f"{order['name']}{mark}: allied with {ally_txt}; rival to {rival_txt}.")
    return "\n".join(lines)
