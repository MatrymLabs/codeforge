"""Test twin for parts/seed.py -- loading, the room template, and the gates."""

import pytest

from parts.seed import (
    DEFAULT_ROOM_DESC,
    SEEDS_ROOT,
    SeedError,
    inspect_world_links,
    load_doors,
    load_items,
    load_npcs,
    load_rooms,
    load_splash,
)
from parts.world import SEED_PATH


def test_an_unplaced_prototype_loads_with_a_nowhere_location(tmp_path):
    itemsf = tmp_path / "items.yaml"
    itemsf.write_text("trophy:\n  location: nowhere\n")
    # a drop-only prototype: never tagged room:, never placed, only spawned by clone()
    assert load_items(itemsf)["trophy"]["location"] == "nowhere"


def test_world_links_accept_a_nowhere_prototype_and_reject_a_bad_drop(tmp_path):
    (tmp_path / "rooms.yaml").write_text("cell:\n")
    (tmp_path / "items.yaml").write_text("trophy:\n  location: nowhere\n")
    (tmp_path / "npcs.yaml").write_text("wight:\n  location: cell\n  hp: 5\n  drops: [trophy]\n")
    rooms = load_rooms(tmp_path / "rooms.yaml")
    items = load_items(tmp_path / "items.yaml")
    npcs = load_npcs(tmp_path / "npcs.yaml")
    inspect_world_links(rooms, items, npcs)  # no raise: unplaced item ok, drop names a real item
    npcs["wight"]["drops"] = ["ghost_item"]  # now a drop that names nothing real
    with pytest.raises(SeedError, match="drops"):
        inspect_world_links(rooms, items, npcs)


def test_aethryn_boss_drops_a_valid_unplaced_prototype():
    root = SEEDS_ROOT / "aethryn"
    rooms = load_rooms(root / "rooms.yaml")
    items = load_items(root / "items.yaml")
    npcs = load_npcs(root / "npcs.yaml")
    inspect_world_links(rooms, items, npcs)  # the whole flagship seed still links cleanly
    assert npcs["cinder_wight"]["drops"] == ["cinder_hammer"]
    assert items["cinder_hammer"]["location"] == "nowhere"  # drop-only, never on the cellar floor


def test_an_npc_drops_list_loads(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 5\n  drops: [cold_shard, ember]\n")
    assert load_npcs(npcsf)["wight"]["drops"] == ["cold_shard", "ember"]


def test_a_plain_npc_carries_no_drops_key(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("rat:\n  location: cell\n")
    assert "drops" not in load_npcs(npcsf)["rat"]  # opt-in: absent unless declared


def test_a_non_list_drops_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  drops: cold_shard\n")
    with pytest.raises(SeedError, match="drops"):
        load_npcs(npcsf)


def test_a_self_closing_door_loads_its_recloses_after(tmp_path):
    doors = tmp_path / "doors.yaml"
    doors.write_text("gate:\n  blocks: [hall, north]\n  key_id: brass_key\n  recloses_after: 4\n")
    assert load_doors(doors)["gate"]["recloses_after"] == 4


def test_a_plain_door_carries_no_recloses_after_key(tmp_path):
    doors = tmp_path / "doors.yaml"
    doors.write_text("gate:\n  blocks: [hall, north]\n")
    assert "recloses_after" not in load_doors(doors)["gate"]  # opt-in: absent unless declared


def test_a_negative_recloses_after_is_rejected(tmp_path):
    doors = tmp_path / "doors.yaml"
    doors.write_text("gate:\n  blocks: [hall, north]\n  recloses_after: -2\n")
    with pytest.raises(SeedError, match="recloses_after"):
        load_doors(doors)


def test_load_splash_returns_the_worlds_own_banner():
    # Splash is world data, loaded by the seed (not the gateway); the first-forge seed's title art.
    splash = load_splash()
    assert "F I R S T   F O R G E" in splash  # the seed's spaced title banner
    assert not splash.endswith("\n")  # trailing newline is stripped for a clean render


def test_shipped_seed_loads_with_core_rooms_linked():
    rooms = load_rooms(SEED_PATH)
    assert {"forge", "courtyard", "library", "archive", "cellar"} <= set(rooms)
    assert rooms["library"]["exits"]["north"] == "archive"


def test_missing_file_raises_seed_error(tmp_path):
    with pytest.raises(SeedError, match="not found"):
        load_rooms(tmp_path / "nope.yaml")


def test_a_negative_npc_atk_is_rejected_at_load(tmp_path):
    from parts.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("brawler:\n  location: courtyard\n  atk: -1\n")
    with pytest.raises(SeedError, match="atk"):
        load_npcs(bad)


def test_a_negative_npc_xp_is_rejected_at_load(tmp_path):
    """xp is awarded on defeat: a negative would DRAIN the victor's XP/JP/TP. Refuse it loud."""
    from parts.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("leech:\n  location: courtyard\n  hp: 1\n  xp: -500\n")
    with pytest.raises(SeedError, match="negative xp"):
        load_npcs(bad)


def test_a_negative_npc_hp_is_rejected_at_load(tmp_path):
    from parts.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("ghost:\n  location: courtyard\n  hp: -5\n")
    with pytest.raises(SeedError, match="negative hp"):
        load_npcs(bad)


def test_an_aggressive_npc_without_atk_is_rejected_at_load(tmp_path):
    """An aggressive NPC that cannot land a blow (atk 0) is a contradiction: refuse loud."""
    from parts.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("poser:\n  location: courtyard\n  hp: 10\n  aggressive: true\n")
    with pytest.raises(SeedError, match="aggressive but has atk"):
        load_npcs(bad)


def test_an_aggressive_npc_without_hp_is_rejected_at_load(tmp_path):
    """An aggressive NPC that cannot be fought back (hp 0) is a contradiction: refuse loud."""
    from parts.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("wraith:\n  location: courtyard\n  atk: 4\n  aggressive: true\n")
    with pytest.raises(SeedError, match="aggressive but has hp"):
        load_npcs(bad)


def test_a_valid_aggressive_npc_loads(tmp_path):
    """A properly-armed aggressive NPC (atk + hp) loads and carries the flag."""
    from parts.seed import load_npcs

    good = tmp_path / "npcs.yaml"
    good.write_text("reaver:\n  location: courtyard\n  hp: 20\n  atk: 5\n  aggressive: true\n")
    reaver = load_npcs(good)["reaver"]
    assert reaver["aggressive"] is True
    assert reaver["atk"] == 5


def test_npcs_are_reactive_by_default(tmp_path):
    """No `aggressive` key means a reactive/passive NPC -- the flag defaults False."""
    from parts.seed import load_npcs

    plain = tmp_path / "npcs.yaml"
    plain.write_text("statue:\n  location: courtyard\n  hp: 10\n  atk: 3\n")
    assert load_npcs(plain)["statue"]["aggressive"] is False


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
    # The unique-key gate must fire under whatever loader is active (see the C-loader test
    # below): a duplicate key is a loud SeedError, never a silent overwrite.
    bad = tmp_path / "rooms.yaml"
    bad.write_text("vault:\n  name: Vault A\nvault:\n  name: Vault B\n")
    with pytest.raises(SeedError, match="Duplicate label 'vault'"):
        load_rooms(bad)


def test_seed_loader_prefers_libyaml(tmp_path):
    # EXP-004: seeds parse through libyaml's CSafeLoader (~13x faster) when available. Pinning
    # this means a regression to the slow pure-Python SafeLoader is visible, and it documents
    # that the duplicate-key gate above runs on the C loader (whose composer keeps duplicates).
    import yaml

    from parts.seed import _UniqueKeyLoader

    if yaml.__with_libyaml__:
        assert issubclass(_UniqueKeyLoader, yaml.CSafeLoader), "seed loader should use libyaml"
    else:  # pragma: no cover - libyaml is present on our hosts and CI
        assert issubclass(_UniqueKeyLoader, yaml.SafeLoader)


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

from parts.seed import SEED_DIR  # noqa: E402


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
        inspect_world_links(rooms, bad_items, {})


def test_cross_gate_catches_npc_in_missing_room(tmp_path):
    rooms = load_rooms(SEED_DIR / "rooms.yaml")
    path = tmp_path / "npcs.yaml"
    path.write_text("ghost:\n  location: the_void\n")
    bad_npcs = load_npcs(path)
    with pytest.raises(SeedError, match="the_void"):
        inspect_world_links(rooms, {}, bad_npcs)


def test_a_resettable_item_loads_the_flag(tmp_path):
    itemsf = tmp_path / "items.yaml"
    itemsf.write_text("shard:\n  location: cave\n  resettable: true\n")
    assert load_items(itemsf)["shard"]["resettable"] is True


def test_a_plain_item_carries_no_resettable_key(tmp_path):
    itemsf = tmp_path / "items.yaml"
    itemsf.write_text("shard:\n  location: cave\n")
    assert "resettable" not in load_items(itemsf)["shard"]  # opt-in: absent unless declared


def test_a_non_bool_resettable_is_rejected(tmp_path):
    itemsf = tmp_path / "items.yaml"
    itemsf.write_text("shard:\n  location: cave\n  resettable: maybe\n")
    with pytest.raises(SeedError, match="resettable"):
        load_items(itemsf)
