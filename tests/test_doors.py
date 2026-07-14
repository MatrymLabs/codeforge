"""Test twin for parts/doors.py -- locks, keys, and gated movement."""

import copy

import pytest

from parts import doors, items
from parts.doors import barred_door_for, unlock
from parts.items import take
from parts.world import resolve_move


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS and DOORS before each test, restore after."""
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)


def test_oak_door_starts_locked():
    assert barred_door_for("library", "north") == "oak_door"


def test_locked_door_blocks_movement():
    arrived, message = resolve_move("library", "north")
    assert arrived == "library"
    assert "locked" in message


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
    arrived, _ = resolve_move("library", "north")
    assert arrived == "archive"


def test_open_gate_opens_a_locked_door_without_a_key():
    """A quest reforging a bridge opens a barrier by engine decree, carrying no key."""
    assert doors.DOORS["oak_door"]["locked"] is True
    assert doors.open_gate("oak_door") is True
    assert doors.DOORS["oak_door"]["locked"] is False
    arrived, _ = resolve_move("library", "north")  # the gate is open now
    assert arrived == "archive"


def test_open_gate_is_a_no_op_on_unknown_or_already_open_doors():
    assert doors.open_gate("no_such_door") is False  # unknown
    doors.open_gate("oak_door")
    assert doors.open_gate("oak_door") is False  # already open -> nothing to do
