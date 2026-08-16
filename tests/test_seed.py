"""Test twin for kernel/world/seed.py -- loading, the room template, and the gates."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from kernel.world.seed import (
    DEFAULT_ROOM_DESC,
    SEEDS_ROOT,
    BlueprintError,
    inspect_world_links,
    load_doors,
    load_items,
    load_npcs,
    load_recipes,
    load_rooms,
    load_splash,
)
from kernel.world.world import SEED_PATH


def _seed_dir_from_env(**updates: str) -> Path:
    env = os.environ.copy()
    for name in (
        "FORGE_BLUEPRINT",
        "FORGE_SEED",
        "CODEFORGE_BLUEPRINTS_ROOT",
        "CODEFORGE_SEEDS_ROOT",
    ):
        env.pop(name, None)
    env.update(updates)
    result = subprocess.run(
        [sys.executable, "-c", "from kernel.world.seed import BLUEPRINT_DIR; print(BLUEPRINT_DIR)"],
        cwd=Path(__file__).parents[1],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def test_legacy_seed_dir_is_the_blueprint_dir_alias():
    from kernel.world.seed import BLUEPRINT_DIR, SEED_DIR

    assert SEED_DIR is BLUEPRINT_DIR


def test_blueprint_and_seed_names_resolve_to_the_same_blueprint():
    old_name = _seed_dir_from_env(FORGE_SEED="aethryn")
    new_name = _seed_dir_from_env(FORGE_BLUEPRINT="aethryn")
    assert old_name == new_name


def test_new_blueprint_name_wins_when_both_names_are_set():
    resolved = _seed_dir_from_env(FORGE_BLUEPRINT="spiral-ascent", FORGE_SEED="aethryn")
    assert resolved.name == "spiral-ascent"


def test_blueprint_and_seed_root_names_resolve_to_the_same_root(tmp_path):
    (tmp_path / "solo-game").mkdir()
    (tmp_path / "solo-game" / "rooms.yaml").write_text("start:\n")
    old_root = _seed_dir_from_env(CODEFORGE_SEEDS_ROOT=str(tmp_path), FORGE_SEED="solo-game")
    new_root = _seed_dir_from_env(
        CODEFORGE_BLUEPRINTS_ROOT=str(tmp_path), FORGE_BLUEPRINT="solo-game"
    )
    assert old_root == new_root


def test_blueprint_error_is_the_only_legacy_error_spelling():
    legacy_name = "Seed" + "Error"
    root = Path(__file__).parents[1]
    source_files = sorted(
        path
        for path in root.rglob("*.py")
        if not {".git", ".venv", "__pycache__"}.intersection(path.parts)
    )
    occurrences = [
        (path.relative_to(root), line_number, line.strip())
        for path in source_files
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if legacy_name in line
    ]
    assert len(occurrences) == 1, occurrences
    assert occurrences[0][0] == Path("kernel/world/seed.py")
    assert occurrences[0][2] == f"{legacy_name} = BlueprintError"


def test_legacy_error_alias_preserves_the_module_boundary():
    import kernel.world.seed as seed_module

    assert getattr(seed_module, "Seed" + "Error") is BlueprintError


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
    with pytest.raises(BlueprintError, match="drops"):
        inspect_world_links(rooms, items, npcs)


def test_aethryn_boss_drops_a_valid_unplaced_prototype():
    root = SEEDS_ROOT / "aethryn"
    rooms = load_rooms(root / "rooms.yaml")
    items = load_items(root / "items.yaml")
    npcs = load_npcs(root / "npcs.yaml")
    inspect_world_links(rooms, items, npcs)  # the whole flagship seed still links cleanly
    assert npcs["netharions_throne_guardian"]["drops"] == [
        "greater_healing_draught",
        "abyssal_legguards",  # the raid drops the top-tier leg + feet gear
        "abyssal_sabatons",
    ]
    assert items["greater_healing_draught"]["location"] == "nowhere"  # drop-only prototype


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
    with pytest.raises(BlueprintError, match="drops"):
        load_npcs(npcsf)


def test_a_levelled_foe_loads_its_level_and_tier(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wolf:\n  location: cell\n  hp: 15\n  atk: 3\n  level: 3\n  tier: normal\n")
    wolf = load_npcs(npcsf)["wolf"]
    assert wolf["level"] == 3
    assert wolf["tier"] == "normal"


def test_a_levelled_foe_without_a_tier_defaults_to_normal(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wolf:\n  location: cell\n  hp: 15\n  level: 3\n")  # tier omitted
    assert load_npcs(npcsf)["wolf"]["tier"] == "normal"


def test_a_levelless_foe_carries_no_level_or_tier_key(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("rat:\n  location: cell\n  hp: 5\n  xp: 10\n")
    rat = load_npcs(npcsf)["rat"]
    assert "level" not in rat and "tier" not in rat  # opt-in: absent keeps the flat economy


def test_an_out_of_range_level_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wolf:\n  location: cell\n  hp: 15\n  level: 999\n")
    with pytest.raises(BlueprintError, match="level"):
        load_npcs(npcsf)


def test_an_unknown_tier_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wolf:\n  location: cell\n  hp: 15\n  level: 3\n  tier: legendary\n")
    with pytest.raises(BlueprintError, match="tier"):
        load_npcs(npcsf)


def test_a_typed_foe_loads_its_attack_element(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 20\n  atk: 5\n  attack_element: FIR\n")
    assert load_npcs(npcsf)["wight"]["attack_element"] == "FIR"


def test_a_plain_foe_carries_no_attack_element_key(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("rat:\n  location: cell\n  hp: 5\n")
    assert "attack_element" not in load_npcs(npcsf)["rat"]  # opt-in: untyped unless declared


def test_an_unknown_attack_element_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 20\n  atk: 5\n  attack_element: PLASMA\n")
    with pytest.raises(BlueprintError, match="attack_element"):
        load_npcs(npcsf)


def test_a_foe_resistance_grid_loads(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 20\n  resistances: {FIR: Immune, ICE: Weak}")
    assert load_npcs(npcsf)["wight"]["resistances"] == {"FIR": "Immune", "ICE": "Weak"}


def test_a_plain_foe_carries_no_resistances_key(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("rat:\n  location: cell\n  hp: 5\n")
    assert "resistances" not in load_npcs(npcsf)["rat"]  # opt-in: resists nothing unless declared


def test_a_foe_resistance_with_a_bad_code_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 20\n  resistances: {XYZ: Weak}\n")
    with pytest.raises(BlueprintError, match="resistance code"):
        load_npcs(npcsf)


def test_a_foe_resistance_with_a_bad_level_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 20\n  resistances: {FIR: Squishy}\n")
    with pytest.raises(BlueprintError, match="resistance"):
        load_npcs(npcsf)


def test_a_non_mapping_resistances_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 20\n  resistances: fireproof\n")
    with pytest.raises(BlueprintError, match="resistances"):
        load_npcs(npcsf)


def test_a_tier_without_a_level_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wolf:\n  location: cell\n  hp: 15\n  tier: boss\n")  # nothing to scale
    with pytest.raises(BlueprintError, match="tier"):
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
    with pytest.raises(BlueprintError, match="recloses_after"):
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
    with pytest.raises(BlueprintError, match="not found"):
        load_rooms(tmp_path / "nope.yaml")


def test_a_negative_npc_atk_is_rejected_at_load(tmp_path):
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("brawler:\n  location: courtyard\n  atk: -1\n")
    with pytest.raises(BlueprintError, match="atk"):
        load_npcs(bad)


def test_a_negative_npc_xp_is_rejected_at_load(tmp_path):
    """xp is awarded on defeat: a negative would DRAIN the victor's XP/JP/TP. Refuse it loud."""
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("leech:\n  location: courtyard\n  hp: 1\n  xp: -500\n")
    with pytest.raises(BlueprintError, match="negative xp"):
        load_npcs(bad)


def test_a_negative_npc_hp_is_rejected_at_load(tmp_path):
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("ghost:\n  location: courtyard\n  hp: -5\n")
    with pytest.raises(BlueprintError, match="negative hp"):
        load_npcs(bad)


def test_an_aggressive_npc_without_atk_is_rejected_at_load(tmp_path):
    """An aggressive NPC that cannot land a blow (atk 0) is a contradiction: refuse loud."""
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("poser:\n  location: courtyard\n  hp: 10\n  aggressive: true\n")
    with pytest.raises(BlueprintError, match="aggressive but has atk"):
        load_npcs(bad)


def test_an_aggressive_npc_without_hp_is_rejected_at_load(tmp_path):
    """An aggressive NPC that cannot be fought back (hp 0) is a contradiction: refuse loud."""
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text("wraith:\n  location: courtyard\n  atk: 4\n  aggressive: true\n")
    with pytest.raises(BlueprintError, match="aggressive but has hp"):
        load_npcs(bad)


def test_a_valid_aggressive_npc_loads(tmp_path):
    """A properly-armed aggressive NPC (atk + hp) loads and carries the flag."""
    from kernel.world.seed import load_npcs

    good = tmp_path / "npcs.yaml"
    good.write_text("reaver:\n  location: courtyard\n  hp: 20\n  atk: 5\n  aggressive: true\n")
    reaver = load_npcs(good)["reaver"]
    assert reaver["aggressive"] is True
    assert reaver["atk"] == 5


def test_a_raid_without_tier_boss_is_rejected_at_load(tmp_path):
    """A raid flag on a non-boss is a contradiction: a raid rides the boss curve + weekly lock."""
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text(
        "impostor:\n  location: courtyard\n  hp: 30\n  atk: 5\n  level: 10\n"
        "  tier: elite\n  raid: true\n"
    )
    with pytest.raises(BlueprintError, match="raid.*must be tier 'boss'"):
        load_npcs(bad)


def test_a_valid_raid_boss_loads_and_carries_the_flag(tmp_path):
    """A boss-tier foe flagged raid loads with raid=True (the weekly party objective)."""
    from kernel.world.seed import load_npcs

    good = tmp_path / "npcs.yaml"
    good.write_text(
        "abyss_guardian:\n  location: courtyard\n  hp: 900\n  atk: 40\n  level: 300\n"
        "  tier: boss\n  raid: true\n  lethal: true\n"
    )
    guardian = load_npcs(good)["abyss_guardian"]
    assert guardian["raid"] is True
    assert guardian["tier"] == "boss"


def test_npcs_are_reactive_by_default(tmp_path):
    """No `aggressive` key means a reactive/passive NPC -- the flag defaults False."""
    from kernel.world.seed import load_npcs

    plain = tmp_path / "npcs.yaml"
    plain.write_text("statue:\n  location: courtyard\n  hp: 10\n  atk: 3\n")
    assert load_npcs(plain)["statue"]["aggressive"] is False


def test_dangling_exit_is_rejected_at_load(tmp_path):
    bad = tmp_path / "rooms.yaml"
    bad.write_text("start:\n  exits:\n    north: mystery_cave\n")
    with pytest.raises(BlueprintError, match="mystery_cave"):
        load_rooms(bad)


def test_invalid_label_is_rejected_with_suggestion(tmp_path):
    bad = tmp_path / "rooms.yaml"
    bad.write_text("North Tower:\n  name: North Tower\n")
    with pytest.raises(BlueprintError, match="north_tower"):
        load_rooms(bad)


def test_duplicate_label_is_rejected(tmp_path):
    # The unique-key gate must fire under whatever loader is active (see the C-loader test
    # below): a duplicate key is a loud BlueprintError, never a silent overwrite.
    bad = tmp_path / "rooms.yaml"
    bad.write_text("vault:\n  name: Vault A\nvault:\n  name: Vault B\n")
    with pytest.raises(BlueprintError, match="Duplicate label 'vault'"):
        load_rooms(bad)


@pytest.mark.parametrize("yaml_text", ["? ?", "? [a]"])
def test_unusable_mapping_keys_are_rejected_as_seed_errors(yaml_text):
    from kernel.world.seed import _UniqueKeyLoader

    with pytest.raises(BlueprintError, match="Unusable key in Blueprint file"):
        yaml.load(yaml_text, Loader=_UniqueKeyLoader)


def test_seed_loader_prefers_libyaml(tmp_path):
    # EXP-004: seeds parse through libyaml's CSafeLoader (~13x faster) when available. Pinning
    # this means a regression to the slow pure-Python SafeLoader is visible, and it documents
    # that the duplicate-key gate above runs on the C loader (whose composer keeps duplicates).
    import yaml

    from kernel.world.seed import _UniqueKeyLoader

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

from kernel.world.seed import BLUEPRINT_DIR  # noqa: E402


def test_shipped_items_seed_loads_the_copper_key():
    items = load_items(BLUEPRINT_DIR / "items.yaml")
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
    with pytest.raises(BlueprintError, match="missing required field 'location'"):
        load_items(path)


def test_shipped_npcs_seed_loads_the_librarian():
    npcs = load_npcs(BLUEPRINT_DIR / "npcs.yaml")
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
    rooms = load_rooms(BLUEPRINT_DIR / "rooms.yaml")
    path = tmp_path / "items.yaml"
    path.write_text("lost_coin:\n  location: mystery_cave\n")
    bad_items = load_items(path)
    with pytest.raises(BlueprintError, match="mystery_cave"):
        inspect_world_links(rooms, bad_items, {})


def test_cross_gate_catches_npc_in_missing_room(tmp_path):
    rooms = load_rooms(BLUEPRINT_DIR / "rooms.yaml")
    path = tmp_path / "npcs.yaml"
    path.write_text("ghost:\n  location: the_void\n")
    bad_npcs = load_npcs(path)
    with pytest.raises(BlueprintError, match="the_void"):
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
    with pytest.raises(BlueprintError, match="resettable"):
        load_items(itemsf)


def test_an_npc_loot_table_loads(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  hp: 5\n  loot: {shard: 3, nothing: 7}\n")
    assert load_npcs(npcsf)["wight"]["loot"] == {"shard": 3, "nothing": 7}


def test_a_plain_npc_carries_no_loot_key(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("rat:\n  location: cell\n")
    assert "loot" not in load_npcs(npcsf)["rat"]  # opt-in: absent unless declared


def test_a_non_positive_loot_weight_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("wight:\n  location: cell\n  loot: {shard: 0}\n")
    with pytest.raises(BlueprintError, match="loot"):
        load_npcs(npcsf)


def test_world_links_reject_a_loot_naming_a_missing_item(tmp_path):
    (tmp_path / "rooms.yaml").write_text("cell:\n")
    (tmp_path / "items.yaml").write_text("shard:\n  location: cell\n")
    (tmp_path / "npcs.yaml").write_text(
        "wight:\n  location: cell\n  hp: 5\n  loot: {shard: 1, nothing: 2}\n"
    )
    rooms = load_rooms(tmp_path / "rooms.yaml")
    items = load_items(tmp_path / "items.yaml")
    npcs = load_npcs(tmp_path / "npcs.yaml")
    inspect_world_links(rooms, items, npcs)  # ok: shard is real, `nothing` is the reserved no-drop
    npcs["wight"]["loot"] = {"ghost": 1}
    with pytest.raises(BlueprintError, match="loot"):
        inspect_world_links(rooms, items, npcs)


def test_a_valid_shop_loads_its_sells_and_buys(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text(
        "trader:\n  location: cell\n  shop:\n    sells: {gem: 10}\n    buys: {ore: 3}\n"
    )
    trader = load_npcs(npcsf)["trader"]
    assert trader["shop"]["sells"] == {"gem": 10} and trader["shop"]["buys"] == {"ore": 3}


def test_a_plain_npc_carries_no_shop_key(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("rat:\n  location: cell\n")
    assert "shop" not in load_npcs(npcsf)["rat"]  # opt-in: absent unless declared


def test_a_shop_with_a_nonpositive_price_is_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("trader:\n  location: cell\n  shop:\n    sells: {gem: 0}\n")
    with pytest.raises(BlueprintError, match="shop"):
        load_npcs(npcsf)


def test_a_shop_naming_an_unknown_prototype_is_rejected_at_boot(tmp_path):
    (tmp_path / "rooms.yaml").write_text("cell:\n")
    (tmp_path / "items.yaml").write_text("gem:\n  location: cell\n")
    (tmp_path / "npcs.yaml").write_text(
        "trader:\n  location: cell\n  shop:\n    sells: {ghost: 5}\n"
    )
    rooms = load_rooms(tmp_path / "rooms.yaml")
    its = load_items(tmp_path / "items.yaml")
    ns = load_npcs(tmp_path / "npcs.yaml")
    with pytest.raises(BlueprintError, match="shop sells names"):
        inspect_world_links(rooms, its, ns)


def test_a_consumable_item_loads_its_effect(tmp_path):
    itemsf = tmp_path / "items.yaml"
    itemsf.write_text("potion:\n  location: cell\n  consume: {hp: 30, mp: 10}\n")
    assert load_items(itemsf)["potion"]["consume"] == {"hp": 30, "mp": 10}


def test_a_consumable_with_a_bad_effect_is_rejected(tmp_path):
    itemsf = tmp_path / "items.yaml"
    itemsf.write_text("potion:\n  location: cell\n  consume: {stamina: 5}\n")  # only hp/mp allowed
    with pytest.raises(BlueprintError, match="consume"):
        load_items(itemsf)


def test_npc_topics_load(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("sage:\n  location: cell\n  topics:\n    lore:\n      - The old tale.\n")
    assert load_npcs(npcsf)["sage"]["topics"]["lore"] == ["The old tale."]


def test_npc_topics_with_an_empty_reply_list_are_rejected(tmp_path):
    npcsf = tmp_path / "npcs.yaml"
    npcsf.write_text("sage:\n  location: cell\n  topics:\n    lore: []\n")
    with pytest.raises(BlueprintError, match="topics"):
        load_npcs(npcsf)


def test_load_recipes_returns_none_shape_when_absent(tmp_path):
    assert load_recipes(tmp_path / "recipes.yaml") == {}  # a seed with no maker's loop


def test_load_recipes_accepts_a_wellformed_recipe(tmp_path):
    p = tmp_path / "recipes.yaml"
    p.write_text("mend:\n  name: a draught\n  makes: healing_draught\n  inputs: {ember_shard: 2}\n")
    recipe = load_recipes(p)["mend"]
    assert recipe["makes"] == "healing_draught" and recipe["inputs"] == {"ember_shard": 2}


def test_load_recipes_rejects_a_recipe_with_no_output(tmp_path):
    p = tmp_path / "recipes.yaml"
    p.write_text("bad:\n  inputs: {ember_shard: 2}\n")  # no 'makes'
    with pytest.raises(BlueprintError, match="makes"):
        load_recipes(p)


def test_load_recipes_rejects_a_nonpositive_input_count(tmp_path):
    p = tmp_path / "recipes.yaml"
    p.write_text("bad:\n  makes: healing_draught\n  inputs: {ember_shard: 0}\n")
    with pytest.raises(BlueprintError, match="inputs"):
        load_recipes(p)


def test_load_recipes_rejects_empty_inputs(tmp_path):
    p = tmp_path / "recipes.yaml"
    p.write_text("bad:\n  makes: healing_draught\n  inputs: {}\n")
    with pytest.raises(BlueprintError, match="inputs"):
        load_recipes(p)


def test_an_aggressive_wanderer_is_rejected_at_load(tmp_path):
    """A wanderer must be peaceful: an aggressive NPC that drifts would flee a fight it opened."""
    from kernel.world.seed import load_npcs

    bad = tmp_path / "npcs.yaml"
    bad.write_text(
        "beast:\n  location: cell\n  hp: 10\n  atk: 5\n  aggressive: true\n  wander: true\n"
    )
    with pytest.raises(BlueprintError, match="wander.*peaceful|peaceful"):
        load_npcs(bad)


def test_a_valid_wanderer_loads_and_carries_the_flag(tmp_path):
    """A peaceful ambient NPC flagged wander loads with wander=True."""
    from kernel.world.seed import load_npcs

    good = tmp_path / "npcs.yaml"
    good.write_text("critter:\n  location: cell\n  hp: 3\n  wander: true\n")
    assert load_npcs(good)["critter"]["wander"] is True


def test_reassembles_loads_through_and_marks_the_foe(tmp_path):
    """A foe seeded `reassembles: true` carries the flag into the loaded Npc (the dummy)."""
    seed = tmp_path / "npcs.yaml"
    seed.write_text("dummy:\n  location: courtyard\n  hp: 20\n  reassembles: true\n")
    npcs = load_npcs(seed)
    assert npcs["dummy"].get("reassembles") is True


def test_a_mortal_foe_carries_no_reassembles_flag(tmp_path):
    """Absent `reassembles`, a foe is mortal: the flag is not stamped on by default."""
    seed = tmp_path / "npcs.yaml"
    seed.write_text("wolf:\n  location: courtyard\n  hp: 30\n")
    assert "reassembles" not in load_npcs(seed)["wolf"]


def test_reassembles_on_an_uncombatable_foe_is_rejected_at_load(tmp_path):
    """A reassembling foe that cannot be fought (hp 0) is meaningless: refuse loud."""
    seed = tmp_path / "npcs.yaml"
    seed.write_text("poser:\n  location: courtyard\n  hp: 0\n  reassembles: true\n")
    with pytest.raises(BlueprintError, match="reassembles"):
        load_npcs(seed)


def test_a_non_bool_reassembles_is_rejected_at_load(tmp_path):
    """`reassembles` must be a real bool, not a truthy string -- refuse a bad type loud."""
    seed = tmp_path / "npcs.yaml"
    seed.write_text("poser:\n  location: courtyard\n  hp: 5\n  reassembles: yes-please\n")
    with pytest.raises(BlueprintError, match="reassembles"):
        load_npcs(seed)
