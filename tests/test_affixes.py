"""Test twin for parts.shelf.affixes: the deterministic loot-variety factory (rarity + affixes)."""

from random import Random

from parts.shelf.affixes import Rolled, roll

# The five derived combat stats affixes may target (mirrored locally so this stays an ENGINE-FREE
# shelf twin -- it must not import parts.world, or the pour would hold its test back).
DERIVED_STATS = ("ATK", "DEF", "EVA", "MAG DEF", "ACC")


def test_roll_is_deterministic_given_a_seed():
    a = roll(Random(7), "blade", {"ATK": 10}, 20)
    b = roll(Random(7), "blade", {"ATK": 10}, 20)
    assert a == b and isinstance(a, Rolled)  # no hidden randomness -- reproducible loot


def test_a_common_roll_leaves_the_base_unchanged():
    for seed in range(80):
        r = roll(Random(seed), "blade", {"ATK": 10}, 20)
        if r.rarity == "common":
            assert r.name == "blade" and r.mods == {"ATK": 10}  # no affix, no scaling
            return
    raise AssertionError("expected at least one common roll in 80 tries")


def test_a_rarer_roll_boosts_the_base_and_adds_named_affixes():
    for seed in range(400):
        r = roll(Random(seed), "blade", {"ATK": 10}, 20)
        if r.rarity == "legendary":
            assert r.mods["ATK"] >= 10  # base scaled up by the rarity multiplier
            assert r.name != "blade"  # affixes rename it (a prefix and/or suffix)
            assert all(stat in DERIVED_STATS for stat in r.mods)  # only real combat stats
            return
    raise AssertionError("expected a legendary roll in 400 tries")


def test_the_full_rarity_spread_is_reachable():
    seen = {roll(Random(s), "blade", {"ATK": 5}, 10).rarity for s in range(600)}
    assert {"common", "uncommon", "rare", "epic", "legendary"} <= seen


def test_higher_level_makes_affix_bonuses_larger():
    # a fixed seed's affix picks are the same; only the level bonus differs, so mods must not shrink
    low = roll(Random(3), "blade", {"ATK": 10}, 1)
    high = roll(Random(3), "blade", {"ATK": 10}, 60)
    assert high.rarity == low.rarity and high.name == low.name
    assert sum(high.mods.values()) >= sum(low.mods.values())  # level lifts the affix bonuses
