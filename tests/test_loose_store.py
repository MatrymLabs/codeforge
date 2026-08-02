"""Test twin for kernel/world/loose_store.py -- the stored-loose-inventory adapter.

Acceptance: a saved bag loads back (prototype + rolled name/mods/rarity intact); save REPLACES the
whole bag, not appends. Refusal: a stranger's bag is empty, and save is scoped to its owner,
so emptying one hero's bag never touches another's. Real table, quarantined to tmp by conftest.
"""

from __future__ import annotations

from kernel.world import loose_store


def _snap(prototype: str, name: str, mods: dict | None = None, rarity: str = "common") -> dict:
    return {"prototype": prototype, "name": name, "mods": mods or {}, "rarity": rarity}


def test_a_saved_bag_loads_back_with_its_rolls_intact():
    loose_store.save(
        "ada",
        [
            _snap("forge_wrench", "a modular forge wrench"),
            _snap("warm_cloak", "a Cruel warm cloak [rare]", {"MAG DEF": 8}, "rare"),
        ],
    )
    bag = loose_store.load("ada")
    assert len(bag) == 2
    cloak = next(item for item in bag if item["rarity"] == "rare")
    assert cloak["prototype"] == "warm_cloak"
    assert cloak["name"] == "a Cruel warm cloak [rare]"
    assert cloak["mods"] == {"MAG DEF": 8}  # the rolled affix survived the round trip


def test_save_replaces_the_whole_bag_rather_than_appending():
    loose_store.save("ada", [_snap("first_ember", "first")])
    loose_store.save("ada", [_snap("warm_cloak", "second")])  # a fresh, smaller bag
    bag = loose_store.load("ada")
    assert len(bag) == 1 and bag[0]["prototype"] == "warm_cloak"  # the first bag is gone


def test_a_stranger_carries_an_empty_bag():
    assert loose_store.load("nobody") == []


def test_save_is_scoped_to_its_owner():
    loose_store.save("ada", [_snap("forge_wrench", "hers")])
    loose_store.save("bram", [_snap("warm_cloak", "his")])
    loose_store.save("ada", [])  # ada drops everything
    assert loose_store.load("ada") == []
    assert len(loose_store.load("bram")) == 1  # bram's bag is untouched
