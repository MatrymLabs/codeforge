"""Test twin for parts/world/items.py -- containment and item commands."""

import copy

import pytest

from parts.world import items
from parts.world.items import drop, inventory_text, items_in, take


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS before each test, restore after. No leakage."""
    snapshot = copy.deepcopy(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snapshot)


def test_key_starts_in_library():
    assert "copper_key" in items_in("room:library")


def test_take_moves_key_to_player():
    result = take("key", "library")
    assert "take" in result
    assert items.ITEMS["copper_key"]["location"] == "player"


def test_take_fails_in_wrong_room():
    result = take("key", "forge")
    assert result == "You don't see that here."
    assert items.ITEMS["copper_key"]["location"] == "room:library"


def test_drop_returns_key_to_room():
    take("key", "library")
    result = drop("key", "cellar")
    assert "drop" in result
    assert items.ITEMS["copper_key"]["location"] == "room:cellar"


def test_inventory_empty_then_full():
    assert inventory_text() == "You are carrying nothing."
    take("key", "library")
    assert "copper key" in inventory_text()


# --- object instancing: prototype + clone (Fork A, slice 1) ---------------------------
def test_a_seed_item_is_its_own_prototype():
    assert items.prototype_of("copper_key") == "copper_key"
    assert items.ITEMS["copper_key"].get("prototype") == "copper_key"


def test_clone_mints_a_distinct_instance_from_a_prototype():
    iid = items.clone("copper_key", "forge")
    assert iid != "copper_key" and iid in items.ITEMS  # a fresh instance, not the seed singleton
    inst = items.ITEMS[iid]
    assert inst["prototype"] == "copper_key"
    assert inst["location"] == "room:forge"
    assert inst["name"] == items.PROTOTYPES["copper_key"]["name"]  # template copied
    assert items.prototype_of(iid) == "copper_key"


def test_cloning_twice_yields_two_distinct_instances():
    a = items.clone("copper_key", "forge")
    b = items.clone("copper_key", "forge")
    assert a != b
    assert items.items_in("room:forge").count(a) == 1


def test_clone_accepts_a_room_label_a_tagged_room_or_player():
    assert items.ITEMS[items.clone("copper_key", "forge")]["location"] == "room:forge"
    assert items.ITEMS[items.clone("copper_key", "room:forge")]["location"] == "room:forge"
    assert items.ITEMS[items.clone("copper_key", "player")]["location"] == "player"


def test_cloning_an_unknown_prototype_fails_loud():
    with pytest.raises(items.ItemError, match="unknown item prototype"):
        items.clone("no_such_thing", "forge")


def test_prototype_of_falls_back_to_the_id_for_an_unknown_item():
    assert items.prototype_of("mystery") == "mystery"
