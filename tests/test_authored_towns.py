"""Test twin for parts/world/authored_towns.py -- the hand-authored settlement pipeline.

Acceptance: the pipeline discovers every authored town file, and for each builds its interior
(subareas + residents + items) as records that compose onto the REAL generated aethryn map -- the
hub opens into the town, every interior room is reachable, and every placement resolves. Greenhold,
the first town through it, keeps its shape (four subareas, a peaceful keeper, a valid foe, a
takeable old-world key) and its quest still walks enter -> take -> enter to done. Refusal: no-op
for a world without a town's hub (a non-aethryn seed), and a malformed authored file (missing
section, a foreign exit, a resident or item in a non-town room, an aggressive foe with no attack)
fails loud with the town named.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.world import authored_towns as towns
from parts.world.seed import Room, SeedError, load_rooms

_AETHRYN = Path(__file__).resolve().parent.parent / "seeds" / "aethryn"
_AUTHORED = _AETHRYN / "authored"
_GH = _AUTHORED / "greenhold.yaml"

_GH_INTERIOR = {
    "greenhold_market",
    "greenhold_smithy",
    "greenhold_granary",
    "greenhold_undercroft",
    "greenhold_fields",
}


# --- Acceptance: the pipeline discovers and builds every authored town ----------------------------


def test_the_pipeline_finds_the_authored_towns():
    files = towns.town_files(_AUTHORED)
    assert _GH in files
    assert all(p.suffix == ".yaml" for p in files)


def test_every_authored_town_builds_and_its_exits_stay_within_the_town():
    for path in towns.town_files(_AUTHORED):
        rooms, npcs, items = towns.raise_town(path)
        assert rooms and npcs  # a town has rooms and at least one resident
        hub = towns._load(path)["hub"]["room"]
        known = set(rooms) | {hub}
        for label, room in rooms.items():
            for direction, dest in room["exits"].items():
                assert dest in known, f"{path.stem}: {label} {direction} -> {dest} strands the town"
        for npc in npcs.values():
            assert npc["location"] in rooms
        for item in items.values():
            assert item["location"].split(":")[-1] in rooms


def test_greenhold_is_a_dense_authored_town():
    rooms, npcs, items = towns.raise_town(_GH)
    assert set(rooms) == _GH_INTERIOR  # five subareas incl. the fields
    # Multiple voices: a keeper, a miller, a gossip (peaceful, with topics), and two foes.
    talkers = [n for n in npcs.values() if n["hp"] == 0 and n.get("topics")]
    assert len(talkers) >= 3
    foes = [n for n in npcs.values() if n.get("aggressive")]
    assert {"greenhold_vermin", "greenhold_boar"} <= set(npcs)
    assert len(foes) == 2 and all(f["hp"] > 0 and f["atk"] > 0 for f in foes)
    # Side content: a quest item AND a readable parish record (environmental storytelling).
    assert "lore" in items["greenhold_valve_key"]
    assert "lore" in items["greenhold_parish_record"]
    # Reactivity: NPCs cross-reference each other and the town's mysteries.
    assert any("beast" in n.get("topics", {}) for n in npcs.values())


# --- Acceptance: it composes onto the real generated aethryn map ----------------------------------


def test_authored_towns_compose_into_the_real_aethryn_map():
    world = load_rooms(_AETHRYN / "rooms.yaml")  # the real generated map, which holds the hubs
    npcs: dict = {}
    items = towns.install_authored_towns(world, npcs, _AUTHORED)
    assert items and npcs  # something installed

    for path in towns.town_files(_AUTHORED):
        rooms, _, _ = towns.raise_town(path)
        hub = towns._load(path)["hub"]["room"]
        # Every interior room merged, every exit resolves, and the hub opens into the town.
        for label in rooms:
            assert label in world
            for direction, dest in world[label]["exits"].items():
                assert dest in world, f"{path.stem}: {label} {direction} -> {dest} dead in the map"
        seen, frontier = {hub}, [hub]
        while frontier:
            for dest in world[frontier.pop()]["exits"].values():
                if dest in world and dest not in seen and dest in rooms:
                    seen.add(dest)
                    frontier.append(dest)
        assert set(rooms) <= seen, f"{path.stem}: not every subarea reachable from its hub"


def _walk_quest(quest_file: str):
    """Load an authored town's quest and walk enter -> take -> enter to done; return the final
    Fired outcome. Every authored town's arc uses the same natural-trigger shape."""
    from parts.shelf.workflow import Fired, Instance, WorkflowEngine
    from parts.world.quest import _from_seed
    from parts.world.seed import load_quest

    spec = load_quest(_AETHRYN / "quests" / quest_file)
    assert spec is not None
    workflow, _, reward = _from_seed(spec)
    engine = WorkflowEngine(workflow)
    run = Instance(workflow.workflow_id, spec["start"], [], {})
    assert isinstance(engine.advance(run, "enter"), Fired)  # meet the giver
    assert isinstance(engine.advance(run, "take"), Fired)  # recover the item
    finish = engine.advance(run, "enter")  # return to the giver
    assert isinstance(finish, Fired) and engine.is_done(run)
    return finish, reward


def test_the_granary_quest_still_walks_to_done_and_rewards():
    finish, reward = _walk_quest("greenhold_intro.yaml")
    assert reward == 40
    assert "award_xp" in (finish.effect or "") and "grant_rep:making" in (finish.effect or "")


def test_greenholds_second_quest_is_a_hunt_of_a_different_shape():
    # The field-beast quest is enter -> DEFEAT (a hunt), not a fetch: quest variety.
    from parts.shelf.workflow import Fired, Instance, WorkflowEngine
    from parts.world.quest import _from_seed
    from parts.world.seed import load_quest

    spec = load_quest(_AETHRYN / "quests" / "greenhold_fields.yaml")
    assert spec is not None and spec["name"] == "The Field-Beast"
    events = {step["event"] for step in spec["steps"]}
    assert "defeat" in events and "take" not in events  # a hunt, not a fetch
    engine = WorkflowEngine(_from_seed(spec)[0])
    run = Instance(spec["id"], spec["start"], [], {})
    assert isinstance(engine.advance(run, "enter"), Fired)  # into the fields
    finish = engine.advance(run, "defeat")  # fell the boar
    assert isinstance(finish, Fired) and engine.is_done(run)
    assert "grant_rep:gathering" in (finish.effect or "")


def test_the_brightwater_quest_walks_to_done_and_rewards():
    finish, reward = _walk_quest("brightwater_sluice.yaml")
    assert reward == 55
    assert "award_xp" in (finish.effect or "") and "grant_rep:knowing" in (finish.effect or "")


def test_the_moltenhold_quest_walks_to_done_and_rewards():
    finish, reward = _walk_quest("moltenhold_foundry.yaml")
    assert reward == 110
    assert "award_xp" in (finish.effect or "") and "grant_rep:warcraft" in (finish.effect or "")


def test_the_wildgrowth_quest_walks_and_grants_gathering():
    finish, reward = _walk_quest("wildgrowth_root.yaml")
    assert reward == 70
    assert "grant_rep:gathering" in (finish.effect or "")


def test_the_frosthold_quest_walks_and_grants_warcraft():
    finish, reward = _walk_quest("frosthold_observatory.yaml")
    assert reward == 80
    assert "grant_rep:warcraft" in (finish.effect or "")


def test_the_lumengrotto_quest_walks_and_grants_knowing():
    finish, reward = _walk_quest("lumengrotto_archive.yaml")
    assert reward == 100
    assert "grant_rep:knowing" in (finish.effect or "")


def test_the_ravenwatch_quest_walks_and_grants_knowing():
    finish, reward = _walk_quest("ravenwatch_barrow.yaml")
    assert reward == 32 and "grant_rep:knowing" in (finish.effect or "")


def test_ravenwatch_has_a_second_quest_of_a_hunt_shape():
    from parts.shelf.workflow import Fired, Instance, WorkflowEngine
    from parts.world.quest import _from_seed
    from parts.world.seed import load_quest

    spec = load_quest(_AETHRYN / "quests" / "ravenwatch_hollow.yaml")
    assert spec is not None and spec["name"] == "The Hollow Man"
    assert {step["event"] for step in spec["steps"]} == {"enter", "defeat"}  # a hunt
    engine = WorkflowEngine(_from_seed(spec)[0])
    run = Instance(spec["id"], spec["start"], [], {})
    assert isinstance(engine.advance(run, "enter"), Fired)
    finish = engine.advance(run, "defeat")
    assert isinstance(finish, Fired) and engine.is_done(run)
    assert "grant_rep:gathering" in (finish.effect or "")


def _walk_hunt(quest_file: str, order: str, reward: int) -> None:
    """Walk an authored town's HUNT-shape side quest: enter -> defeat -> done. Asserts the shape (a
    defeat, no fetch), the reward, and the granted Order. The second-quest twin of _walk_quest."""
    from parts.shelf.workflow import Fired, Instance, WorkflowEngine
    from parts.world.quest import _from_seed
    from parts.world.seed import load_quest

    spec = load_quest(_AETHRYN / "quests" / quest_file)
    assert spec is not None and spec["reward_xp"] == reward
    events = {step["event"] for step in spec["steps"]}
    assert "defeat" in events and "take" not in events  # a hunt, not a fetch: quest-shape variety
    engine = WorkflowEngine(_from_seed(spec)[0])
    run = Instance(spec["id"], spec["start"], [], {})
    assert isinstance(engine.advance(run, "enter"), Fired)
    finish = engine.advance(run, "defeat")
    assert isinstance(finish, Fired) and engine.is_done(run)
    assert f"grant_rep:{order}" in (finish.effect or "")


def test_brightwaters_second_quest_is_a_warcraft_hunt():
    _walk_hunt("brightwater_weir.yaml", "warcraft", 42)


def test_wildgrowths_second_quest_is_a_warcraft_hunt():
    _walk_hunt("wildgrowth_thorns.yaml", "warcraft", 65)


def test_frostholds_second_quest_is_a_gathering_hunt():
    _walk_hunt("frosthold_shelf.yaml", "gathering", 75)


def test_batch_a_towns_carry_a_vendor_a_node_and_a_working_economy():
    # Density-v2: each deepened town gains a working economy (a vendor who SELLS supplies and BUYS
    # the town's own gather-node yield), a gather node, a third voice, a second danger, and a second
    # lore item -- the Greenhold density standard, now with the pipeline's vendor + node.
    for stem, material in (
        ("brightwater", "meadowfoil"),
        ("wildgrowth", "fernshade"),
        ("frosthold", "frostmoss"),
    ):
        rooms, npcs, items = towns.raise_town(_AUTHORED / f"{stem}.yaml")
        vendors = [n for n in npcs.values() if n.get("shop")]
        assert len(vendors) == 1, f"{stem}: exactly one vendor"
        shop = vendors[0]["shop"]
        assert shop.get("sells"), f"{stem}: the vendor sells supplies"
        assert shop.get("buys", {}).get(material), f"{stem}: the vendor buys its own node's yield"
        assert any(r.get("node") == material for r in rooms.values()), f"{stem}: a {material} node"
        talkers = [n for n in npcs.values() if n["hp"] == 0 and n.get("topics")]
        assert len(talkers) >= 3, f"{stem}: three reactive voices"
        assert len([n for n in npcs.values() if n.get("aggressive")]) >= 2, f"{stem}: two dangers"
        assert len([i for i in items.values() if "lore" in i]) >= 2, f"{stem}: two lore items"


def test_the_sunscar_quest_walks_and_grants_gathering():
    finish, reward = _walk_quest("sunscar_charter.yaml")
    assert reward == 85 and "grant_rep:gathering" in (finish.effect or "")


def test_the_zulkarak_quest_walks_and_grants_making():
    finish, reward = _walk_quest("zulkarak_physic.yaml")
    assert reward == 90 and "grant_rep:making" in (finish.effect or "")


def test_the_voidspire_endgame_quest_walks_and_grants_warcraft():
    finish, reward = _walk_quest("voidspire_threshold.yaml")
    assert reward == 200  # the endgame staging quest pays the most
    assert "grant_rep:warcraft" in (finish.effect or "")


def test_the_stonefang_quest_walks_and_grants_making():
    finish, reward = _walk_quest("stonefang_drift.yaml")
    assert reward == 95 and "grant_rep:making" in (finish.effect or "")


def test_the_stonehelm_quest_walks_and_grants_warcraft():
    finish, reward = _walk_quest("stonehelm_order.yaml")
    assert reward == 140 and "grant_rep:warcraft" in (finish.effect or "")


def test_the_stormreach_quest_walks_and_grants_gathering():
    finish, reward = _walk_quest("stormreach_gate.yaml")
    assert reward == 165 and "grant_rep:gathering" in (finish.effect or "")


def test_the_aurelian_quest_walks_and_grants_knowing():
    finish, reward = _walk_quest("aurelian_nexus.yaml")
    assert reward == 185 and "grant_rep:knowing" in (finish.effect or "")


def test_every_canon_region_has_an_authored_town():
    # The content spine: a hand-authored place in every one of the fourteen reaches.
    import yaml

    from parts.world import canon
    from parts.world.seed import _UniqueKeyLoader

    settlements = yaml.load(
        (_AETHRYN / "settlements.yaml").read_text(encoding="utf-8"), Loader=_UniqueKeyLoader
    )
    covered = set()
    for path in towns.town_files(_AUTHORED):
        hub = towns._load(path)["hub"]["room"]
        covered.add(settlements[hub]["zone"])  # the region name the town's hub sits in
    assert covered == canon.locked_region_names(), (
        f"reaches without an authored town: {canon.locked_region_names() - covered}"
    )


def test_the_four_orders_are_each_granted_by_an_authored_quest():
    # Across the authored towns, every Order is earnable, so the reputation web is reachable.
    from parts.world.seed import load_quest

    effects = " ".join(
        step.get("effect", "")
        for name in (
            "greenhold_intro",
            "brightwater_sluice",
            "moltenhold_foundry",
            "wildgrowth_root",
            "frosthold_observatory",
            "lumengrotto_archive",
        )
        for step in (load_quest(_AETHRYN / "quests" / f"{name}.yaml") or {}).get("steps", [])
    )
    for order in ("making", "knowing", "warcraft", "gathering"):
        assert f"grant_rep:{order}" in effects, f"no authored quest grants {order}"


# --- Refusal: the guard and the loud failures ----------------------------------------------------


def test_install_is_a_no_op_without_any_hub():
    world: dict = {}  # a world that is not aethryn: no town hubs
    npcs: dict = {}
    assert towns.install_authored_towns(world, npcs, _AUTHORED) == {}
    assert world == {} and npcs == {}  # nothing merged


def test_install_merges_the_town_whose_hub_is_present():
    world: dict = {"greenhold": Room(name="Greenhold", desc="hub", exits={"out": "veridia"})}
    npcs: dict = {}
    items = towns.install_authored_towns(world, npcs, _AUTHORED)
    assert set(world) >= _GH_INTERIOR and "greenhold_valve_key" in items
    assert "greenhold_keeper" in npcs
    assert world["greenhold"]["exits"]["square"] == "greenhold_market"


def test_town_files_of_a_missing_dir_is_empty(tmp_path: Path):
    assert towns.town_files(tmp_path / "nope") == []


def test_authored_foes_keep_their_region_element():
    # Regression: the pipeline once dropped attack_element, so elemental foes loaded UNTYPED and the
    # score sheet's resistance grid never engaged. Every authored region-foe must keep its element.
    for town, foe, element in (
        ("moltenhold", "moltenhold_construct", "FIR"),
        ("frosthold", "frosthold_revenant", "ICE"),
        ("stormreach", "stormreach_drowned", "WTR"),
        ("aurelian_city", "aurelian_drone", "LGT"),
    ):
        _, npcs, _ = towns.raise_town(_AUTHORED / f"{town}.yaml")
        assert npcs[foe]["attack_element"] == element


def test_the_pipeline_carries_a_gather_node_and_a_vendor_shop(tmp_path: Path):
    # Density capability: authored rooms may hold a gather node, and authored NPCs a vendor shop.
    body = (
        "rooms: {harbor_market: {name: M, desc: d, exits: {out: harborville}, node: iron_ore}}\n"
        "hub: {room: harborville, keyword: square, entry: harbor_market}\n"
        "npcs: {harbor_broker: {name: V, keywords: [v], location: harbor_market, "
        "shop: {sells: {relic: 50}}}}\n"
        "items: {harbor_relic: {name: k, keywords: [k], location: harbor_market}}\n"
    )
    rooms, npcs, _ = towns.raise_town(_write(tmp_path, body))
    assert rooms["harbor_market"]["node"] == "iron_ore"
    assert npcs["harbor_broker"]["shop"] == {"sells": {"relic": 50}}


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "harborville.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_a_missing_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not found"):
        towns.raise_town(tmp_path / "nope.yaml")


def test_a_non_mapping_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not a mapping"):
        towns.raise_town(_write(tmp_path, "- just\n- a\n- list\n"))


def test_a_missing_section_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="missing or empty section"):
        towns.raise_town(_write(tmp_path, "rooms: {a: {name: A, desc: d, exits: {}}}\n"))


_BASE = (
    "rooms: {harbor_market: {name: M, desc: d, exits: {out: harborville}}}\n"
    "hub: {room: harborville, keyword: square, entry: harbor_market}\n"
    "npcs: {harbor_keeper: {name: W, keywords: [w], location: harbor_market}}\n"
    "items: {harbor_relic: {name: k, keywords: [k], location: harbor_market}}\n"
)


def test_a_well_formed_town_builds_and_an_item_without_lore_is_fine(tmp_path: Path):
    rooms, npcs, items = towns.raise_town(_write(tmp_path, _BASE))
    assert set(rooms) == {"harbor_market"} and "harbor_keeper" in npcs
    assert "lore" not in items["harbor_relic"]  # lore is optional


def test_an_exit_to_a_foreign_room_fails_loud(tmp_path: Path):
    body = _BASE.replace("exits: {out: harborville}", "exits: {north: mordor}")
    with pytest.raises(SeedError, match="not a room of this town"):
        towns.raise_town(_write(tmp_path, body))


def test_a_resident_outside_the_town_fails_loud(tmp_path: Path):
    body = _BASE.replace("location: harbor_market}}\nitems", "location: elsewhere}}\nitems")
    with pytest.raises(SeedError, match="npc .*not a town room"):
        towns.raise_town(_write(tmp_path, body))


def test_an_item_outside_the_town_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: k, keywords: [k], location: harbor_market}",
        "{name: k, keywords: [k], location: elsewhere}",
    )
    with pytest.raises(SeedError, match="item .*not a town room"):
        towns.raise_town(_write(tmp_path, body))


def test_an_aggressive_foe_with_no_attack_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: W, keywords: [w], location: harbor_market}",
        "{name: F, keywords: [f], location: harbor_market, aggressive: true, hp: 10}",
    )
    with pytest.raises(SeedError, match="needs hp > 0 and atk > 0"):
        towns.raise_town(_write(tmp_path, body))


def test_a_room_missing_a_field_fails_loud(tmp_path: Path):
    body = _BASE.replace("{name: M, desc: d, exits: {out: harborville}}", "{name: M, exits: {}}")
    with pytest.raises(SeedError, match="needs a name, desc, and exits"):
        towns.raise_town(_write(tmp_path, body))


def test_an_npc_missing_keywords_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: W, keywords: [w], location: harbor_market}", "{name: W, location: harbor_market}"
    )
    with pytest.raises(SeedError, match="npc .*needs a name and keywords"):
        towns.raise_town(_write(tmp_path, body))


def test_an_item_missing_keywords_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: k, keywords: [k], location: harbor_market}", "{name: k, location: harbor_market}"
    )
    with pytest.raises(SeedError, match="item .*needs a name and keywords"):
        towns.raise_town(_write(tmp_path, body))


def test_wire_is_a_no_op_when_the_hub_is_absent():
    world: dict = {}
    towns.wire_town(world, _GH)
    assert world == {}
