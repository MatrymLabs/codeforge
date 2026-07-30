"""Test twin for parts/world/greenhold.py + the Greenhold slice (rooms, people, item, quest).

Acceptance: the authored interior builds four subareas with a peaceful keeper, a valid foe, and a
takeable old-world key; every interior exit resolves to a Greenhold room or the hub; composed onto
the REAL generated aethryn map, the hub opens into the town and every interior room is reachable and
every placement resolves; and the quest arc walks enter -> take -> enter to done, awarding XP and
standing. Refusal: install is a no-op on a world without the Greenhold hub (a non-aethryn seed), and
a malformed authored file (missing section, a foreign exit, a resident in a non-Greenhold room, an
aggressive foe with no attack) fails loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.world import greenhold
from parts.world.seed import Room, SeedError, load_rooms

_AETHRYN = Path(__file__).resolve().parent.parent / "seeds" / "aethryn"
_GH = _AETHRYN / "greenhold.yaml"

_INTERIOR = {"greenhold_market", "greenhold_smithy", "greenhold_granary", "greenhold_undercroft"}


# --- Acceptance: the authored interior builds -----------------------------------------------------


def test_raise_greenhold_builds_the_interior():
    rooms, npcs, items = greenhold.raise_greenhold(_GH)
    assert set(rooms) == _INTERIOR
    assert set(npcs) == {"greenhold_keeper", "greenhold_vermin"}
    assert set(items) == {"greenhold_valve_key"}


def test_every_interior_exit_resolves_to_an_interior_or_the_hub():
    rooms, _, _ = greenhold.raise_greenhold(_GH)
    known = set(rooms) | {"greenhold"}
    for label, room in rooms.items():
        for direction, dest in room["exits"].items():
            assert dest in known, f"{label} {direction} -> {dest} strands the town"


def test_the_keeper_is_peaceful_and_the_vermin_are_a_valid_foe():
    _, npcs, _ = greenhold.raise_greenhold(_GH)
    assert npcs["greenhold_keeper"]["hp"] == 0  # a keeper is never a fight
    assert npcs["greenhold_keeper"].get("topics")  # she holds a real conversation
    vermin = npcs["greenhold_vermin"]
    assert vermin.get("aggressive") and vermin["hp"] > 0 and vermin["atk"] > 0


def test_the_valve_key_is_a_takeable_old_world_item():
    _, _, items = greenhold.raise_greenhold(_GH)
    key = items["greenhold_valve_key"]
    assert key["location"] == "room:greenhold_undercroft"  # placed, so it can be taken
    assert "lore" in key  # readable environmental storytelling, a clue to the old world


# --- Acceptance: it composes onto the real generated aethryn map ----------------------------------


def test_greenhold_composes_into_the_real_aethryn_map():
    world = load_rooms(_AETHRYN / "rooms.yaml")  # the real generated map, which holds the hub
    assert "greenhold" in world
    rooms, npcs, items = greenhold.raise_greenhold(_GH)
    world.update(rooms)
    greenhold.wire_greenhold(world, _GH)

    # Every Greenhold exit resolves in the combined map (the closure load_rooms could not check).
    for label in [*rooms, "greenhold"]:
        for direction, dest in world[label]["exits"].items():
            assert dest in world, f"{label} {direction} -> {dest} is a dead link in the map"

    # The hub opens into the town, and every interior room is reachable from it.
    assert world["greenhold"]["exits"].get("square") == "greenhold_market"
    seen, frontier = {"greenhold"}, ["greenhold"]
    while frontier:
        for dest in world[frontier.pop()]["exits"].values():
            if dest in world and dest not in seen and dest.startswith("greenhold"):
                seen.add(dest)
                frontier.append(dest)
    assert seen >= _INTERIOR  # all four subareas reachable from the hub

    # Placements resolve (the inspect_world_links contract, applied to Greenhold).
    for npc in npcs.values():
        assert npc["location"] in world
    for item in items.values():
        assert item["location"].split(":")[-1] in world


# --- Acceptance: the quest arc walks end to end ---------------------------------------------------


def test_the_granary_quest_walks_to_done_and_rewards():
    from parts.shelf.workflow import Fired, Instance, WorkflowEngine
    from parts.world.quest import _from_seed
    from parts.world.seed import load_quest

    spec = load_quest(_AETHRYN / "quests" / "greenhold_intro.yaml")
    assert spec is not None and spec["name"] == "The Granary's Thirst"

    workflow, name, reward = _from_seed(spec)
    assert reward == 40
    engine = WorkflowEngine(workflow)
    run = Instance(workflow.workflow_id, spec["start"], [], {})

    # enter the granary (meet Wenna) -> take the key -> return to the granary -> done.
    assert isinstance(engine.advance(run, "enter"), Fired)  # offered -> accepted
    assert isinstance(engine.advance(run, "take"), Fired)  # accepted -> recovered
    finish = engine.advance(run, "enter")  # recovered -> done
    assert isinstance(finish, Fired)
    assert engine.is_done(run)
    assert "award_xp" in (finish.effect or "") and "grant_rep:making" in (finish.effect or "")


def test_the_quest_starts_and_ends_on_natural_triggers_not_a_verb():
    # No `accept` event (which would collide with the bare `quest accept` of another arc): the arc
    # is driven entirely by entering the granary and taking the key.
    from parts.world.seed import load_quest

    spec = load_quest(_AETHRYN / "quests" / "greenhold_intro.yaml")
    events = {step["event"] for step in spec["steps"]}
    assert events == {"enter", "take"} and "accept" not in events
    triggers = {step.get("on_enter") or step.get("on_take") for step in spec["steps"]}
    assert "greenhold_granary" in triggers and "greenhold_valve_key" in triggers


# --- Refusal: the guard and the loud failures ----------------------------------------------------


def test_install_is_a_no_op_without_the_hub():
    world: dict = {}  # a world that is not aethryn: no Greenhold hub
    npcs: dict = {}
    assert greenhold.install_greenhold(world, npcs, _GH) == {}
    assert world == {} and npcs == {}  # nothing merged


def test_install_merges_when_the_hub_is_present():
    world: dict = {"greenhold": Room(name="Greenhold", desc="hub", exits={"out": "veridia"})}
    npcs: dict = {}
    items = greenhold.install_greenhold(world, npcs, _GH)
    assert set(world) >= _INTERIOR and "greenhold_valve_key" in items
    assert "greenhold_keeper" in npcs
    assert world["greenhold"]["exits"]["square"] == "greenhold_market"


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "greenhold.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_a_missing_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not found"):
        greenhold.raise_greenhold(tmp_path / "nope.yaml")


def test_a_missing_section_fails_loud(tmp_path: Path):
    body = "rooms: {greenhold_market: {name: M, desc: d, exits: {out: greenhold}}}\n"
    with pytest.raises(SeedError, match="missing or empty section"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_an_exit_to_a_foreign_room_fails_loud(tmp_path: Path):
    body = (
        "rooms: {greenhold_market: {name: M, desc: d, exits: {north: mordor}}}\n"
        "hub: {room: greenhold, keyword: square, entry: greenhold_market}\n"
        "npcs: {greenhold_keeper: {name: W, keywords: [w], location: greenhold_market}}\n"
        "items: {k: {name: k, keywords: [k], location: greenhold_market}}\n"
    )
    with pytest.raises(SeedError, match="not a Greenhold room"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_a_resident_outside_greenhold_fails_loud(tmp_path: Path):
    body = (
        "rooms: {greenhold_market: {name: M, desc: d, exits: {out: greenhold}}}\n"
        "hub: {room: greenhold, keyword: square, entry: greenhold_market}\n"
        "npcs: {greenhold_keeper: {name: W, keywords: [w], location: elsewhere}}\n"
        "items: {k: {name: k, keywords: [k], location: greenhold_market}}\n"
    )
    with pytest.raises(SeedError, match="not a Greenhold room"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_an_aggressive_foe_with_no_attack_fails_loud(tmp_path: Path):
    body = (
        "rooms: {greenhold_market: {name: M, desc: d, exits: {out: greenhold}}}\n"
        "hub: {room: greenhold, keyword: square, entry: greenhold_market}\n"
        "npcs: {greenhold_foe: {name: F, keywords: [f], location: greenhold_market, "
        "aggressive: true, hp: 10}}\n"
        "items: {k: {name: k, keywords: [k], location: greenhold_market}}\n"
    )
    with pytest.raises(SeedError, match="needs hp > 0 and atk > 0"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_a_non_mapping_file_fails_loud(tmp_path: Path):
    with pytest.raises(SeedError, match="not a mapping"):
        greenhold.raise_greenhold(_write(tmp_path, "- just\n- a\n- list\n"))


# A minimal well-formed authored file the field-refusal tests mutate one part of.
_BASE = (
    "rooms: {greenhold_market: {name: M, desc: d, exits: {out: greenhold}}}\n"
    "hub: {room: greenhold, keyword: square, entry: greenhold_market}\n"
    "npcs: {greenhold_keeper: {name: W, keywords: [w], location: greenhold_market}}\n"
    "items: {greenhold_valve_key: {name: k, keywords: [k], location: greenhold_market}}\n"
)


def test_a_room_missing_a_field_fails_loud(tmp_path: Path):
    body = _BASE.replace("{name: M, desc: d, exits: {out: greenhold}}", "{name: M, exits: {}}")
    with pytest.raises(SeedError, match="needs a name, desc, and exits"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_an_npc_missing_a_name_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: W, keywords: [w], location: greenhold_market}", "{location: greenhold_market}"
    )
    with pytest.raises(SeedError, match="npc .*needs a name and keywords"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_an_item_in_a_non_greenhold_room_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: k, keywords: [k], location: greenhold_market}",
        "{name: k, keywords: [k], location: elsewhere}",
    )
    with pytest.raises(SeedError, match="item .*not a Greenhold room"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_an_item_missing_its_keywords_fails_loud(tmp_path: Path):
    body = _BASE.replace(
        "{name: k, keywords: [k], location: greenhold_market}",
        "{name: k, location: greenhold_market}",
    )
    with pytest.raises(SeedError, match="item .*needs a name and keywords"):
        greenhold.raise_greenhold(_write(tmp_path, body))


def test_an_item_without_lore_still_builds(tmp_path: Path):
    # _BASE's item carries no lore: it should build fine (lore is optional).
    _, _, items = greenhold.raise_greenhold(_write(tmp_path, _BASE))
    assert "lore" not in items["greenhold_valve_key"]


def test_wire_is_a_no_op_when_the_hub_is_absent():
    world: dict = {}  # no hub
    greenhold.wire_greenhold(world, _GH)
    assert world == {}  # nothing wired
