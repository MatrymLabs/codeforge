"""Test twin for parts/seed.py -- loading, the room template, and the gates."""

import pytest

from parts.seed import DEFAULT_DESC, SeedError, load_rooms
from parts.world import SEED_PATH


def test_shipped_seed_loads_with_core_rooms_linked():
    rooms = load_rooms(SEED_PATH)
    assert {"forge", "courtyard", "library", "archive", "cellar"} <= set(rooms)
    assert rooms["library"]["exits"]["north"] == "archive"


def test_missing_file_raises_seed_error(tmp_path):
    with pytest.raises(SeedError, match="not found"):
        load_rooms(tmp_path / "nope.yaml")


def test_dangling_exit_is_rejected_at_load(tmp_path):
    bad = tmp_path / "rooms.yaml"
    bad.write_text("start:\n  exits:\n    north: mystery_cave\n")
    with pytest.raises(SeedError, match="mystery_cave"):
        load_rooms(bad)


def test_invalid_label_is_rejected_with_suggestion(tmp_path):
    bad = tmp_path / "rooms.yaml"
    bad.write_text("North Tower:\n  name: North Tower\n")
    with pytest.raises(SeedError, match="north_tower"):
        load_rooms(bad)


def test_duplicate_label_is_rejected(tmp_path):
    bad = tmp_path / "rooms.yaml"
    bad.write_text("vault:\n  name: Vault A\nvault:\n  name: Vault B\n")
    with pytest.raises(SeedError, match="Duplicate label 'vault'"):
        load_rooms(bad)


def test_bare_label_becomes_a_complete_room(tmp_path):
    path = tmp_path / "rooms.yaml"
    path.write_text("north_tower:\n")
    rooms = load_rooms(path)
    assert rooms["north_tower"]["name"] == "North Tower"
    assert rooms["north_tower"]["desc"] == DEFAULT_DESC
    assert rooms["north_tower"]["exits"] == {}


def test_file_template_overrides_engine_defaults(tmp_path):
    path = tmp_path / "rooms.yaml"
    path.write_text("template:\n  desc: Ash drifts in the air here.\nvault:\ncrypt:\n")
    rooms = load_rooms(path)
    assert rooms["vault"]["desc"] == "Ash drifts in the air here."
    assert rooms["crypt"]["desc"] == "Ash drifts in the air here."
    assert rooms["vault"]["name"] == "Vault"  # per-label default still applies


def test_room_fields_win_over_template(tmp_path):
    path = tmp_path / "rooms.yaml"
    path.write_text(
        "template:\n  desc: Ash drifts in the air here.\n"
        "vault:\n  desc: Cold iron shelves line the walls.\n"
    )
    rooms = load_rooms(path)
    assert rooms["vault"]["desc"] == "Cold iron shelves line the walls."
