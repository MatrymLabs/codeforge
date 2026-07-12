"""Test twin for parts/items.py -- containment and item commands."""

import copy

import pytest

from parts import items
from parts.items import drop, inventory_text, items_in, take


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
