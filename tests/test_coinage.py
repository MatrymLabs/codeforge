"""Test twin for kernel/world/coinage.py -- the tiered ember-coin denomination.

Acceptance: a purse denominates into its tiers, largest first, skipping empties, in full and compact
forms, at every scale from a fleck to a fortune. Refusal: a malformed coinage table fails loud.
"""

from __future__ import annotations

import pytest

from kernel.world.coinage import AETHRYN_COINAGE, Coinage, CoinageError, Tier, purse

_BASE = Tier("cinder", "cinders", "c", 1)  # a valid base tier, to isolate other malformations


def test_a_purse_denominates_from_cinders_to_forgemarks():
    assert purse(0) == "0 cinders"
    assert purse(7) == "7 cinders"
    assert purse(1) == "1 cinder"  # singular
    assert purse(145) == "1 spark, 45 cinders"
    assert purse(4567) == "45 sparks, 67 cinders"
    assert purse(1_234_567) == "1 forgemark, 23 embers, 45 sparks, 67 cinders"
    assert purse(50_000_000) == "50 forgemarks"  # empty tiers are skipped


def test_compact_form_uses_symbols():
    assert AETHRYN_COINAGE.format(1_234_567, compact=True) == "1fm 23e 45s 67c"
    assert AETHRYN_COINAGE.format(0, compact=True) == "0 cinders"


def test_a_negative_purse_shows_its_magnitude():
    assert purse(-145) == "-1 spark, 45 cinders"


def test_the_tier_worth_is_the_running_product_of_the_steps():
    # cinder 1, spark 100, ember 10_000, forgemark 1_000_000
    assert AETHRYN_COINAGE._worth == [1, 100, 10_000, 1_000_000]


def test_a_seed_may_define_its_own_coinage():
    # the denomination is data: a two-tier coin works just as well
    coin = Coinage([Tier("bit", "bits", "b", 1), Tier("crown", "crowns", "cr", 12)])
    assert coin.format(25) == "2 crowns, 1 bit"


@pytest.mark.parametrize(
    "tiers, match",
    [
        ([], "at least one tier"),
        ([Tier("cinder", "cinders", "c", 5)], "base tier .* must have per == 1"),
        ([_BASE, Tier("spark", "sparks", "s", 0)], "'per' must be >= 1"),
        ([_BASE, Tier("spark", "sparks", "c", 10)], "must each be unique"),
    ],
)
def test_a_malformed_coinage_fails_loud(tiers, match):
    with pytest.raises(CoinageError, match=match):
        Coinage(tiers)
