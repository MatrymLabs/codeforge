"""Test twin for parts/equipment.py -- gear into slots, modifiers into derived stats.

Acceptance: a carried equippable item goes into its slot, its modifiers raise the derived
stats through the ModifierStack, and the sheet shows it; unequip reverses it. Refusal: a
non-carried, non-equippable, or bad-slot item is refused loud. Plus the loader's equip fields
(defaults + a rejected mod) and engine-tick reachability.
"""

from __future__ import annotations

import copy

import pytest

from forge import handle_command
from parts import items
from parts.character_view import sheet_from_session
from parts.equipment import apply_equipment, equip, equipped_loadout, unequip
from parts.jobs import bind_calling
from parts.seed import SeedError, load_items
from parts.session import Session


@pytest.fixture(autouse=True)
def fresh_world():
    items_snap = copy.deepcopy(items.ITEMS)
    yield
    items.ITEMS = items_snap


def _engineer_with_wrench() -> Session:
    s = Session(player_id="matrym", location="workshop")
    bind_calling(s, "engineer")
    items.ITEMS["forge_wrench"]["location"] = "player"  # carried
    return s


def test_equipping_puts_gear_in_its_slot() -> None:
    s = _engineer_with_wrench()
    out = equip(s, "wrench")
    assert s.equipped["weapon"] == "forge_wrench"
    assert "You equip" in out


def test_equipped_modifiers_raise_the_derived_stats() -> None:
    s = _engineer_with_wrench()
    base = sheet_from_session(s)
    assert base is not None
    equip(s, "wrench")
    worn = sheet_from_session(s)
    assert worn is not None
    assert worn.derived["ATK"] == base.derived["ATK"] + 6  # the wrench's flat ATK mod
    assert worn.derived["ACC"] == base.derived["ACC"] + 3


def test_the_sheet_shows_the_equipped_item() -> None:
    s = _engineer_with_wrench()
    equip(s, "wrench")
    assert equipped_loadout(s).weapon == "a modular forge wrench"


def test_unequip_reverses_it() -> None:
    s = _engineer_with_wrench()
    equip(s, "wrench")
    out = unequip(s, "weapon")
    assert "weapon" not in s.equipped
    assert "You remove" in out


def test_apply_equipment_is_a_no_op_with_nothing_worn() -> None:
    s = _engineer_with_wrench()
    base = {"ATK": 20, "DEF": 10}
    assert apply_equipment(base, s) == base


# --- refusals -------------------------------------------------------------------
def test_equipping_what_you_do_not_carry_is_refused() -> None:
    s = Session(player_id="matrym", location="workshop")
    bind_calling(s, "engineer")
    assert "aren't carrying that" in equip(s, "wrench")


def test_a_non_equippable_item_is_refused() -> None:
    s = Session(player_id="matrym", location="workshop")
    bind_calling(s, "engineer")
    items.ITEMS["rusty_lantern"]["location"] = "player"
    assert "not something you can equip" in equip(s, "lantern")


def test_an_item_declaring_an_unknown_slot_is_refused() -> None:
    s = _engineer_with_wrench()
    items.ITEMS["forge_wrench"]["slot"] = "banana"  # not a real slot
    assert "unknown slot" in equip(s, "wrench")


def test_unequipping_an_empty_slot_is_refused() -> None:
    s = Session(player_id="matrym")
    assert "Nothing is equipped" in unequip(s, "weapon")


# --- loader ---------------------------------------------------------------------
def test_a_plain_item_defaults_to_no_equipment_fields(tmp_path) -> None:
    path = tmp_path / "items.yaml"
    path.write_text("pebble:\n  location: yard\n")
    pebble = load_items(path)["pebble"]
    assert pebble["slot"] == "" and pebble["mods"] == {}


def test_a_non_integer_mod_is_rejected_at_load(tmp_path) -> None:
    path = tmp_path / "items.yaml"
    path.write_text("blade:\n  location: yard\n  slot: weapon\n  mods: {ATK: sharp}\n")
    with pytest.raises(SeedError, match="must be an integer"):
        load_items(path)


# --- engine-tick reachability ---------------------------------------------------
def test_equip_and_unequip_reach_through_the_tick() -> None:
    s = Session(player_id="matrym", location="workshop")
    handle_command(s, "job engineer")
    handle_command(s, "take wrench")
    assert "You equip" in handle_command(s, "equip wrench")
    assert "You remove" in handle_command(s, "unequip weapon")
