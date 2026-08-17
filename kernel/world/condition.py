"""CARD: condition -- a Lens on the hero's PRESENT state: pools, what ails them, where they stand.

The score sheet (kernel/world/score_sheet) is the character's persistent identity - attributes, job,
gear, the slow-changing record. This is its fast-changing mirror: the one readout that answers "how
am I RIGHT NOW?" in a fight. It gathers the transient truth the deeper sheets scatter or hide -- the
current HP/MP/power pools, and the afflictions (venom, bleed, daze) that until now had a renderer
(afflictions.render_afflictions) wired to no verb, so a poisoned hero had no way to see the poison.

One responsibility: compose the present-condition view. It reads live session state and never
mutates (state is canonical; this is a projection). A hero with no calling yet has no pools to
show, and says so honestly. The deeper tables (full sheet, every Order's standing, the trades) keep
their own verbs; this points to them rather than duplicating them.
"""

from __future__ import annotations

from kernel.world.afflictions import render_afflictions
from kernel.world.session import Session


def render_condition(session: Session) -> str:
    """The `condition` verb: an at-a-glance readout of the hero's present state. Vital pools, then
    what ails them (or that they are hale), then their sworn standing, then a pointer to the fuller
    sheets. Returns the no-calling line when they have chosen no path yet (no pools to read)."""
    if session.stats is None or not session.job:
        return "You have no calling yet. Type JOBS to see the paths."

    lines = ["Your condition:"]
    hp, mp = session.resources["hp"], session.resources["mp"]
    pools = f"  HP {hp.current}/{hp.maximum}    MP {mp.current}/{mp.maximum}"
    power = session.resources.get("power")
    if power is not None:
        pools += f"    Power {power.current}/{power.maximum}"
    lines.append(pools)

    ail = render_afflictions(session)  # "Afflicted: venom (2), dazed (1)" or "" when hale
    lines.append("  " + (ail if ail else "Hale: nothing ails you."))

    if session.order:
        from kernel.world.orders import order_name  # noqa: PLC0415
        from kernel.world.reputation import standing_of, tier_for  # noqa: PLC0415

        rep = standing_of(session, session.order)
        lines.append(f"  Sworn to {order_name(session.order)}: {tier_for(rep)} ({rep})")

    lines.append(
        "  (score for the full sheet, standing for every Order, professions for your trades)"
    )
    return "\n".join(lines)
