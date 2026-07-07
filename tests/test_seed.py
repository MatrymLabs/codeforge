"""Test twin for parts/seed.py -- loading, the room template, and the gates."""

import pytest

from parts.seed import DEFAULT_ROOM_DESC, SeedError, load_rooms
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
    assert rooms["north_tower"]["desc"] == DEFAULT_ROOM_DESC
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


# --- items and NPCs join the seed ---

from parts.seed import SEED_DIR, load_items, load_npcs, validate_locations  # noqa: E402


def test_shipped_items_seed_loads_the_copper_key():
    items = load_items(SEED_DIR / "items.yaml")
    assert items["copper_key"]["location"] == "room:library"
    assert items["copper_key"]["name"] == "a copper key"


def test_item_defaults_generate_name_and_keywords(tmp_path):
    path = tmp_path / "items.yaml"
    path.write_text("oak_staff:\n  location: vault\n")
    items = load_items(path)
    assert items["oak_staff"]["name"] == "an oak staff"
    assert items["oak_staff"]["keywords"] == ["oak staff", "oak", "staff"]
    assert items["oak_staff"]["location"] == "room:vault"


def test_item_without_location_is_rejected(tmp_path):
    path = tmp_path / "items.yaml"
    path.write_text("ghost_gem:\n")
    with pytest.raises(SeedError, match="missing required field 'location'"):
        load_items(path)


def test_shipped_npcs_seed_loads_the_librarian():
    npcs = load_npcs(SEED_DIR / "npcs.yaml")
    assert npcs["librarian"]["location"] == "library"
    assert npcs["librarian"]["next_line"] == 0
    assert "dust" in npcs["librarian"]["dialogue"][0]


def test_npc_defaults_generate_name_and_silence(tmp_path):
    path = tmp_path / "npcs.yaml"
    path.write_text("tower_guard:\n  location: gate\n")
    npcs = load_npcs(path)
    assert npcs["tower_guard"]["name"] == "the tower guard"
    assert npcs["tower_guard"]["dialogue"] == ['"..."']


def test_cross_gate_catches_item_in_missing_room(tmp_path):
    rooms = load_rooms(SEED_DIR / "rooms.yaml")
    path = tmp_path / "items.yaml"
    path.write_text("lost_coin:\n  location: mystery_cave\n")
    bad_items = load_items(path)
    with pytest.raises(SeedError, match="mystery_cave"):
        validate_locations(rooms, bad_items, {})


def test_cross_gate_catches_npc_in_missing_room(tmp_path):
    rooms = load_rooms(SEED_DIR / "rooms.yaml")
    path = tmp_path / "npcs.yaml"
    path.write_text("ghost:\n  location: the_void\n")
    bad_npcs = load_npcs(path)
    with pytest.raises(SeedError, match="the_void"):
        validate_locations(rooms, {}, bad_npcs)
