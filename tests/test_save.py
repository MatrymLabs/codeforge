"""Test twin for parts/save.py -- snapshot persistence."""

import copy
import json

import pytest

from parts import doors, items
from parts.doors import unlock
from parts.items import take
from parts.save import awaken_snapshot, seal_snapshot


@pytest.fixture(autouse=True)
def fresh_world():
    """Snapshot ITEMS and DOORS before each test, restore after."""
    items_snap = copy.deepcopy(items.ITEMS)
    doors_snap = copy.deepcopy(doors.DOORS)
    yield
    items.ITEMS = items_snap
    doors.DOORS = doors_snap


def test_save_creates_file(tmp_path):
    path = tmp_path / "save.json"
    seal_snapshot("library", path)
    assert path.exists()


def test_load_without_file_starts_at_forge(tmp_path):
    location, msg = awaken_snapshot(tmp_path / "missing.json")
    assert location == "forge"
    assert "No saved world" in msg


def test_roundtrip_restores_progress(tmp_path):
    path = tmp_path / "save.json"
    take("key", "library")
    unlock("door", "key", "library")
    seal_snapshot("archive", path)

    # wreck the live world, then load should repair it
    items.ITEMS["copper_key"]["location"] = "room:cellar"
    doors.DOORS["oak_door"]["locked"] = True

    location, _ = awaken_snapshot(path)
    assert location == "archive"
    assert items.ITEMS["copper_key"]["location"] == "player"
    assert doors.DOORS["oak_door"]["locked"] is False


def test_load_ignores_unknown_ids(tmp_path):
    path = tmp_path / "save.json"
    ghost_save = {
        "location": "forge",
        "items": {"ghost_item": "player"},
        "doors": {"ghost_door": False},
    }
    path.write_text(json.dumps(ghost_save))
    location, _ = awaken_snapshot(path)
    assert location == "forge"
    assert "ghost_item" not in items.ITEMS
