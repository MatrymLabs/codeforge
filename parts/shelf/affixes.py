"""CARD: affixes -- roll a rarity and named affixes onto a base item (the loot-variety factory).

A base weapon or piece of armour is a fixed prototype; this turns each DROP of it into a varied
instance -- a rarity tier that scales the base mods, plus prefix/suffix affixes that add more -- so
"a notched blade" can fall as "a Cruel notched blade of the Bear [rare]". It is the item-side of the
generation lever (compare parts.world.spiral for the world side): one base yields a spread of gear.

Pure and deterministic given an injected `random.Random` (like parts.shelf.weighted_table), so loot
is reproducible in tests. It knows nothing about the game -- inputs are a name, a mods map, a level,
and an rng; output is a rolled (name, mods, rarity). The caller applies it to a cloned instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

# Rarity: (label, weight, base-mod multiplier, affix count). Rarer = heavier gear, more affixes.
_RARITIES: tuple[tuple[str, int, float, int], ...] = (
    ("common", 60, 1.0, 0),
    ("uncommon", 24, 1.2, 1),
    ("rare", 10, 1.4, 2),
    ("epic", 5, 1.7, 2),
    ("legendary", 1, 2.0, 3),
)

# Affix name -> (derived stat it boosts, base amount before the level bonus). Prefixes lead the
# name, suffixes trail it. All target the five derived combat stats (parts.world.stat_rules).
_PREFIXES: tuple[tuple[str, str, int], ...] = (
    ("Cruel", "ATK", 3),
    ("Keen", "ACC", 3),
    ("Guarded", "DEF", 3),
    ("Warded", "MAG DEF", 3),
    ("Fleet", "EVA", 2),
    ("Savage", "ATK", 4),
)
_SUFFIXES: tuple[tuple[str, str, int], ...] = (
    ("of the Bear", "DEF", 3),
    ("of Fury", "ATK", 4),
    ("of Precision", "ACC", 4),
    ("of the Ward", "MAG DEF", 3),
    ("of the Wind", "EVA", 2),
    ("of Ruin", "ATK", 5),
)


@dataclass(frozen=True)
class Rolled:
    """The outcome of a roll: the display name, the final mods, and the rarity label."""

    name: str
    mods: dict[str, int]
    rarity: str


def _pick_rarity(rng: Random) -> tuple[str, float, int]:
    """Draw a rarity proportional to weight; return (label, multiplier, affix count)."""
    total = sum(weight for _, weight, _, _ in _RARITIES)
    roll = rng.randint(1, total)
    for label, weight, mult, affixes in _RARITIES:
        roll -= weight
        if roll <= 0:
            return label, mult, affixes
    label, _, mult, affixes = _RARITIES[0]  # unreachable; a clean fallback
    return label, mult, affixes


def roll(rng: Random, base_name: str, base_mods: dict[str, int], level: int) -> Rolled:
    """Roll a rarity + affixes onto a base item. Higher `level` makes affix bonuses larger. The base
    mods are scaled by the rarity multiplier, then each affix adds its (level-scaled) bonus."""
    rarity, mult, affix_count = _pick_rarity(rng)
    mods: dict[str, int] = {s: max(1, round(v * mult)) for s, v in base_mods.items()}

    level_bonus = max(0, level) // 5  # every 5 levels, affixes hit one point harder
    prefix, suffix = "", ""
    for i in range(affix_count):
        # alternate prefix/suffix so a name reads "Cruel <base> of the Bear"; at most one of each.
        if i % 2 == 0 and not prefix:
            label, stat, amount = rng.choice(_PREFIXES)
            prefix = label
        elif not suffix:
            label, stat, amount = rng.choice(_SUFFIXES)
            suffix = label
        else:
            label, stat, amount = rng.choice(_PREFIXES + _SUFFIXES)
        mods[stat] = mods.get(stat, 0) + amount + level_bonus

    name = " ".join(part for part in (prefix, base_name, suffix) if part)
    return Rolled(name=name, mods=mods, rarity=rarity)
