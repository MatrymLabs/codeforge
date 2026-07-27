"""CARD: gearsets -- set bonuses: wearing a whole gear set grants a bonus beyond its pieces.

The wide gear pass gives each Reach a themed set (head/body/arm). This rewards COLLECTING one:
when every piece of a set is worn at once, the set grants an extra flat bonus on top of the pieces'
own mods, so a full Stormward loadout beats three unrelated pieces of the same tier. Pure and
data-driven -- the sets live in the seed (sets.yaml), and the bonus is a small pure fold, so a seed
with no sets.yaml simply earns no set bonuses (graceful, never a crash).
"""

from __future__ import annotations

from parts.world.seed import SEED_DIR, GearSet, load_sets

# The seed's gear sets, loaded once at import (like ITEMS/NPCS). Empty when the seed ships no sets.
SETS: dict[str, GearSet] = load_sets(SEED_DIR / "sets.yaml")


def register_sets(new: dict[str, GearSet]) -> None:
    """Fold GENERATED gear sets into the live registry (like items.register_prototypes for loot). A
    generator (parts.world.delve_sets) forges sets from the assembled world after this module's
    import-time load; this makes their bonuses count. Later labels win on a clash, but generated set
    labels are namespaced so they never collide with the seed's authored sets."""
    SETS.update(new)


def active_set_bonuses(
    worn_prototypes: set[str], sets: dict[str, GearSet] | None = None
) -> dict[str, int]:
    """The summed flat bonus a character earns from every gear set they wear IN FULL.

    `worn_prototypes` is the set of item prototype labels currently equipped; a set contributes its
    `bonus` only when ALL of its pieces are present (a partial set earns nothing). Pure: `sets`
    defaults to the loaded registry, but tests inject their own. Bonuses across sets sum per stat.
    """
    registry = SETS if sets is None else sets
    bonus: dict[str, int] = {}
    for gear_set in registry.values():
        if set(gear_set["pieces"]) <= worn_prototypes:
            for stat, amount in gear_set["bonus"].items():
                bonus[stat] = bonus.get(stat, 0) + amount
    return bonus
