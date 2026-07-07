"""Test twin for parts/doors.py -- locks, keys, and gated movement."""

import copy

import pytest
from parts.doors import door_blocking, unlock

from parts import doors, items
from parts.items import take
from parts.world import try_move


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS and DOORS before each test, restore after."""
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap


def test_oak_door_starts_locked():
    assert door_blocking("library", "north") == "oak_door"


def test_locked_door_blocks_movement():
    assert try_move("library", "north") == "library"


def test_unlock_fails_without_key():
    result = unlock("door", "key", "library")
    assert result == "You aren't carrying that."
    assert doors.DOORS["oak_door"]["locked"] is True


def test_unlock_with_carried_key_succeeds():
    take("key", "library")
    result = unlock("door", "key", "library")
    assert "unlock" in result
    assert doors.DOORS["oak_door"]["locked"] is False


def test_unlocked_door_allows_movement():
    take("key", "library")
    unlock("door", "key", "library")
    assert try_move("library", "north") == "archive"
