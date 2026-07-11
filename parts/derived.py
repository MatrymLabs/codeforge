"""CARD: derived -- derived combat statistics from the six attributes (PROTOTYPE BALANCE).

The score sheet shows five derived stats (ATK, DEF, EVA, MAG DEF, ACC). No formulas existed
for them in the repo, so these are deterministic PROTOTYPE formulas -- `prototype_balance_only`,
NOT final balance (see ADR-0006). They are pure and integer-valued, so every number is exact
and pinned by the test twin; when real balance is designed, only this module changes.

Inputs are the six attributes (strength, speed, magic, stamina, wisdom, luck) plus the
character level. Equipment and status modifiers are NOT folded in yet -- that is the modifier
stack, a later batch (the Evennia kernel's ModifierStack is the salvage target).
"""

from __future__ import annotations

from collections.abc import Mapping

# The derived stats this module computes, in canonical sheet order.
DERIVED_STATS = ("ATK", "DEF", "EVA", "MAG DEF", "ACC")

_BASE_ACCURACY = 70  # prototype: a baseline hit rating before agility/luck adjustments


def derived_stats(attributes: Mapping[str, int], level: int) -> dict[str, int]:
    """Compute the five derived combat stats. PROTOTYPE balance -- deterministic, not final.

    A missing attribute reads 0 rather than raising: the sheet must render a partial character.
    """

    def attr(name: str) -> int:
        return int(attributes.get(name, 0))

    strength, speed = attr("strength"), attr("speed")
    magic, stamina = attr("magic"), attr("stamina")
    wisdom, luck = attr("wisdom"), attr("luck")
    lvl = max(0, int(level))

    return {
        "ATK": round(strength * 2 + speed * 0.5) + lvl,
        "DEF": round(stamina * 1.5) + lvl,
        "EVA": round(speed * 1.2 + luck * 0.5),
        "MAG DEF": round((magic + wisdom) * 0.9),
        "ACC": _BASE_ACCURACY + round(speed * 0.5 + luck * 0.3),
    }
