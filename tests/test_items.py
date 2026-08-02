"""Test twin for kernel/world/items.py -- containment and item commands."""

import copy

import pytest

from kernel.world import items
from kernel.world.items import carrier, drop, inventory_text, items_in, read_item, take

_ME = carrier("hero")  # one hero's per-player inventory tag


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
    result = take("key", "library", _ME)
    assert "take" in result
    assert items.ITEMS["copper_key"]["location"] == _ME


def test_take_fails_in_wrong_room():
    result = take("key", "forge", _ME)
    assert result == "You don't see that here."
    assert items.ITEMS["copper_key"]["location"] == "room:library"


def test_drop_returns_key_to_room():
    take("key", "library", _ME)
    result = drop("key", "cellar", _ME)
    assert "drop" in result
    assert items.ITEMS["copper_key"]["location"] == "room:cellar"


def test_read_shows_an_items_lore():
    items.ITEMS["tome"] = {
        "name": "a dusty tome",
        "keywords": ["tome"],
        "location": "room:library",
        "slot": "",
        "mods": {},
        "lore": "Once, the world was warm.",
    }
    out = read_item("tome", "library", _ME)
    assert "a dusty tome" in out and "Once, the world was warm." in out


def test_read_prefers_a_carried_item_over_one_in_the_room():
    items.ITEMS["note"] = {
        "name": "a carried note",
        "keywords": ["note"],
        "location": _ME,
        "slot": "",
        "mods": {},
        "lore": "carry me",
    }
    assert "carry me" in read_item("note", "anywhere", _ME)  # reads from the hand, no room needed


def test_read_a_thing_with_no_writing_says_so():
    out = read_item("key", "library", _ME)  # the copper key carries no lore
    assert "nothing written" in out


def test_read_a_thing_not_present_is_refused():
    assert read_item("dragon", "library", _ME) == "You don't see that to read."


def test_read_nothing_asks_what():
    assert read_item("  ", "library", _ME) == "Read what?"


def test_inventory_empty_then_full():
    assert inventory_text(_ME) == "You are carrying nothing."
    take("key", "library", _ME)
    assert "copper key" in inventory_text(_ME)


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


def test_two_heroes_do_not_share_one_inventory():
    """The point of per-player inventory: each hero's carrier tag is distinct, so what one takes the
    other never sees. A shared \"player\" bucket would fail this."""
    alia, bram = carrier("alia"), carrier("bram")
    items.ITEMS["gem"] = {
        "name": "a gem",
        "keywords": ["gem"],
        "location": "room:forge",
        "slot": "",
        "mods": {},
    }
    take("gem", "forge", alia)  # alia picks it up
    assert items_in(alia) == ["gem"] and items_in(bram) == []  # bram's bag is untouched
    assert "a gem" in inventory_text(alia) and inventory_text(bram) == "You are carrying nothing."
