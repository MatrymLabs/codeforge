"""CARD: weighted_table -- pick an outcome by weight (loot tables, spawn tables, weighted sampling).

The MUD tradition's loot/spawn table: a foe drops sword (rare) or gold (common) or nothing, an area
spawns a wolf more often than a bear. Underneath it is textbook weighted random selection over a
cumulative distribution -- an original implementation of a generic algorithm, applied as the loot
table the game needs. It never owns a clock or a random source: the caller passes a `random.Random`,
so combat and every other consumer stay deterministic under a seeded RNG in tests.

    table = WeightedTable([("sword", 1), ("gold", 4), (None, 5)])   # None = "nothing"
    table.pick(random.Random(0))    # -> an outcome, drawn proportional to weight

One mechanism, many jobs:
- game: a loot drop on defeat, a weighted spawn, a random encounter.
- general: any weighted choice from a fixed distribution (A/B bucketing, sampled test inputs,
  load spread across weighted backends) with a seedable, reproducible draw.
"""

from __future__ import annotations

from collections.abc import Sequence
from random import Random


class WeightedTableError(ValueError):
    """A malformed table (empty, or a non-positive weight): fail loud, never sample garbage."""


class WeightedTable[T]:
    """A fixed set of outcomes, each with a positive integer weight; `pick` draws one proportional
    to its weight from an injected RNG. Immutable after construction."""

    def __init__(self, entries: Sequence[tuple[T, int]]) -> None:
        entries = tuple(entries)
        if not entries:
            raise WeightedTableError("a weighted table needs at least one outcome")
        for outcome, weight in entries:
            if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
                raise WeightedTableError(
                    f"weight for outcome {outcome!r} must be a positive integer, got {weight!r}"
                )
        self._entries: tuple[tuple[T, int], ...] = entries
        self._total: int = sum(weight for _, weight in entries)

    @property
    def total(self) -> int:
        """The sum of all weights (the denominator of the distribution)."""
        return self._total

    def pick(self, rng: Random) -> T:
        """Draw one outcome, proportional to weight, using the caller's RNG (so the draw is
        reproducible under a seed). A single O(n) walk of the cumulative distribution."""
        roll = rng.randint(1, self._total)
        upto = 0
        for outcome, weight in self._entries:
            upto += weight
            if roll <= upto:
                return outcome
        raise WeightedTableError("unreachable: roll exceeded total weight")  # pragma: no cover
