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

from parts.seed import SEED_DIR
from parts.stat_rules import DERIVED_STATS, Ruleset, apply_ruleset
from parts.world_manifest import load_ruleset

__all__ = ["DERIVED_STATS", "derived_stats"]

# The ACTIVE balance, bound at import from the booted world's world.yaml `rules:` block (or the
# default prototype balance when it declares none) -- the same seed-defined-at-import pattern as
# world.START_ROOM. This is where #292 (WorldManifest) and #293 (stat rulesets) meet: a world's
# declared balance actually reaches the sheet and combat, no call site threading a ruleset.
_ACTIVE_RULESET: Ruleset = load_ruleset(SEED_DIR)


def derived_stats(
    attributes: Mapping[str, int], level: int, ruleset: Ruleset | None = None
) -> dict[str, int]:
    """Compute the five derived combat stats under a ruleset (default = the active world's balance).

    A missing attribute reads 0 rather than raising: the sheet must render a partial character.
    """
    return apply_ruleset(ruleset if ruleset is not None else _ACTIVE_RULESET, attributes, level)
