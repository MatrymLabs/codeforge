"""CARD: coinage -- denominate the purse into a readable, tiered currency (Aethryn's ember-coin).

The economy already had a working purse: a single persisted `coins` scalar earned from kills and
spent at shops. That scalar stays the atomic truth (nothing about wealth changes); this only expands
how it reads. Rather than clone gold/silver/copper, Aethryn's coin is struck from cooled ember, in
four tiers that scale from a beginner's pocket to a legendary hoard:

    CINDER (base) -> SPARK (100 cinders) -> EMBER (100 sparks) -> FORGEMARK (100 embers)

So 1,234,567 cinders reads "1 forgemark, 23 embers, 45 sparks, 67 cinders" (or compact "1fm 23e 45s
67c"). Decimal steps keep it easy to understand, communicate, and display; a new player deals in
cinders and sparks, a veteran in embers and forgemarks, and the same scalar carries both without a
second balance to track. The tiers are DATA (a `Coinage` table), so a seed can define its own coin;
`AETHRYN_COINAGE` is the flagship default. Pure and side-effect-free: it only formats a number.

Denomination does not create or destroy wealth -- inflation control lives in the sinks (shops,
repairs, taxes), a separate concern. This module answers only "how is a purse shown".
"""

from __future__ import annotations

from typing import NamedTuple


class Tier(NamedTuple):
    """One coin tier: its singular/plural names, a short symbol, and how many of the tier BELOW make
    one of it (the base tier's `per` is 1)."""

    name: str
    plural: str
    symbol: str
    per: int


class CoinageError(ValueError):
    """A coinage table was declared malformed (empty, a non-positive step, or a duplicate). Loud."""


class Coinage:
    """A currency: an ascending list of tiers from the base up. Formats a scalar amount into its
    tiers, greedily from the largest. The value of each tier in base units is the running product of
    the `per` steps, so the table is the single source of the denomination."""

    def __init__(self, tiers: list[Tier]) -> None:
        if not tiers:
            raise CoinageError("a coinage needs at least one tier (the base unit).")
        if tiers[0].per != 1:
            raise CoinageError(f"the base tier {tiers[0].name!r} must have per == 1.")
        names = [t.name for t in tiers] + [t.symbol for t in tiers]
        if len(names) != len(set(names)):
            raise CoinageError("coinage tier names and symbols must each be unique.")
        value = 1
        worth: list[int] = []
        for tier in tiers:
            if tier.per < 1:
                raise CoinageError(f"tier {tier.name!r}: 'per' must be >= 1, got {tier.per}.")
            value *= tier.per
            worth.append(value)
        self.tiers = tiers
        self._worth = worth  # each tier's value in base units, base-first

    @property
    def base(self) -> Tier:
        """The smallest coin (the unit the persisted scalar counts)."""
        return self.tiers[0]

    def format(self, amount: int, compact: bool = False) -> str:
        """Denominate `amount` base coins into its tiers, largest first, skipping empty tiers. A
        negative amount is shown as its magnitude with a leading '-'; zero is '0 <base plural>'."""
        if amount < 0:
            return "-" + self.format(-amount, compact)
        if amount == 0:
            return f"0 {self.base.plural}"
        parts: list[str] = []
        remainder = amount
        for tier, worth in zip(reversed(self.tiers), reversed(self._worth), strict=True):
            count, remainder = divmod(remainder, worth)
            if count:
                if compact:
                    parts.append(f"{count}{tier.symbol}")
                else:
                    parts.append(f"{count} {tier.name if count == 1 else tier.plural}")
        return (" " if compact else ", ").join(parts)


# The flagship coinage: ember-struck, four decimal tiers from a fleck to a fortune.
AETHRYN_COINAGE = Coinage(
    [
        Tier("cinder", "cinders", "c", 1),
        Tier("spark", "sparks", "s", 100),
        Tier("ember", "embers", "e", 100),
        Tier("forgemark", "forgemarks", "fm", 100),
    ]
)


def purse(coins: int, coinage: Coinage = AETHRYN_COINAGE) -> str:
    """The player-facing denomination of a purse (e.g. '1 ember, 23 sparks, 45 cinders')."""
    return coinage.format(coins)
