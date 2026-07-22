"""CARD: derived -- derived combat statistics from the six attributes (PROTOTYPE BALANCE).

The score sheet shows five derived stats (ATK, DEF, EVA, MAG DEF, ACC). No formulas existed
for them in the repo, so these are deterministic PROTOTYPE formulas -- `prototype_balance_only`,
NOT final balance (see ADR-0006). They are pure and integer-valued, so every number is exact
and pinned by the test twin.

The balance itself now lives in parts/stat_rules as a typed, configurable Ruleset -- this module
is the stable entry point that applies it. By default it applies DEFAULT_RULESET, which is
byte-identical to the old hardcoded formulas (pinned by a parity test); pass a `ruleset` to run a
world's declared balance instead. Equipment and status modifiers are NOT folded in here -- that is
the modifier stack (a later batch).
"""

from __future__ import annotations

from collections.abc import Mapping

from parts.stat_rules import DEFAULT_RULESET, DERIVED_STATS, Ruleset, apply_ruleset

__all__ = ["DERIVED_STATS", "derived_stats"]


def derived_stats(
    attributes: Mapping[str, int], level: int, ruleset: Ruleset | None = None
) -> dict[str, int]:
    """Compute the five derived combat stats under a ruleset (default = the prototype balance).

    A missing attribute reads 0 rather than raising: the sheet must render a partial character.
    """
    return apply_ruleset(ruleset if ruleset is not None else DEFAULT_RULESET, attributes, level)
