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

_GH_INTERIOR = {"greenhold_market", "greenhold_smithy", "greenhold_granary", "greenhold_undercroft"}


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


def test_greenhold_keeps_its_authored_shape():
    rooms, npcs, items = towns.raise_town(_GH)
    assert set(rooms) == _GH_INTERIOR
    assert npcs["greenhold_keeper"]["hp"] == 0 and npcs["greenhold_keeper"].get("topics")
    vermin = npcs["greenhold_vermin"]
    assert vermin.get("aggressive") and vermin["hp"] > 0 and vermin["atk"] > 0
    key = items["greenhold_valve_key"]
    assert key["location"] == "room:greenhold_undercroft" and "lore" in key


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
