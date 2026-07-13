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
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    doors.DOORS.clear()
    doors.DOORS.update(doors_snap)


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


# --- refusal: hostile / drifted save files degrade honestly, never a stack trace ---


def test_a_corrupt_save_starts_fresh_with_an_honest_message(tmp_path):
    bad = tmp_path / "save.json"
    bad.write_text("{ not json at all")
    location, message = awaken_snapshot(bad)
    assert location  # a real start room, not a crash
    assert "corrupt" in message.lower()
    assert bad.exists()  # the file is left untouched for post-mortem


def test_a_save_from_a_newer_schema_is_refused_gracefully(tmp_path):
    newer = tmp_path / "save.json"
    newer.write_text(json.dumps({"schema_version": 99, "location": "somewhere"}))
    location, message = awaken_snapshot(newer)
    assert "newer version" in message
    assert location != "somewhere"  # a v99 shape is not trusted


def test_a_legacy_versionless_save_still_loads(tmp_path):
    # Every save written before schema_version existed lacks the key: it IS v1 and must load.
    legacy = tmp_path / "save.json"
    legacy.write_text(json.dumps({"location": "courtyard", "items": {}, "doors": {}}))
    location, message = awaken_snapshot(legacy)
    assert location == "courtyard"
    assert "Loaded" in message


def test_a_partial_save_missing_keys_degrades_not_crashes(tmp_path):
    partial = tmp_path / "save.json"
    partial.write_text(json.dumps({"schema_version": 1}))  # no location/items/doors
    location, message = awaken_snapshot(partial)
    assert location  # falls back to the start room
    assert "Loaded" in message


def test_seal_stamps_the_schema_version(tmp_path):
    path = tmp_path / "save.json"
    seal_snapshot("courtyard", path)
    assert json.loads(path.read_text())["schema_version"] == 1
