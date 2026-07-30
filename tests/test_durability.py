"""Test twin for parts/world/durability.py -- gear wears and breaks; repair is the coin sink.

Acceptance: a gear piece reads full until worn, wears (floored at 0), breaks at 0, and repairs to
full; repair_cost/repair_session charge coins per point and mend everything worn. Consequence: a
broken piece grants no stat mods (equipment) and combat wears the weapon on a strike and the body
on a blow. Persistence: durability rides the snapshot worn gear and the bag both use, so wear lasts
a save/restore. Refusal: a non-gear item never wears; a short purse or a whole kit refuses loud.
"""

from __future__ import annotations

import copy

import pytest

from parts.world import durability, items
from parts.world.characters import reclone_item, snapshot_item
from parts.world.equipment import equip, gear_score
from parts.world.jobs import bind_calling
from parts.world.session import Session


@pytest.fixture(autouse=True)
def fresh_items():
    snap = copy.deepcopy(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snap)


def _engineer_with_wrench() -> Session:
    s = Session(player_id="matrym", location="workshop")
    bind_calling(s, "engineer")
    items.ITEMS["forge_wrench"]["location"] = items.carrier("matrym")  # carried
    return s


# --- the durability primitive -------------------------------------------------------------------


def test_a_fresh_piece_reads_full():
    assert durability.current("forge_wrench") == durability.MAX


def test_wear_erodes_and_floors_at_zero():
    durability.wear("forge_wrench", 30)
    assert durability.current("forge_wrench") == durability.MAX - 30
    durability.wear("forge_wrench", 999)
    assert durability.current("forge_wrench") == 0  # floored, never negative
    assert durability.is_broken("forge_wrench")


def test_a_non_gear_item_never_wears_or_repairs():
    items.ITEMS["rusty_lantern"]["durability"] = durability.MAX  # a non-slot item
    durability.wear("rusty_lantern", 50)
    assert durability.current("rusty_lantern") == durability.MAX  # unchanged: not gear
    assert not durability.is_broken("rusty_lantern")
    assert durability.repair("rusty_lantern") == 0  # nothing to repair on a non-gear item


def test_repair_restores_to_full_and_reports_the_points():
    durability.wear("forge_wrench", 40)
    restored = durability.repair("forge_wrench")
    assert restored == 40
    assert durability.current("forge_wrench") == durability.MAX
    assert durability.repair("forge_wrench") == 0  # already full: nothing restored


# --- broken gear grants no mods -----------------------------------------------------------------


def test_a_broken_piece_grants_no_gear_score():
    s = _engineer_with_wrench()
    equip(s, "wrench")
    assert gear_score(s) == 9  # ATK 6 + ACC 3 while whole
    durability.wear(s.equipped["weapon"], durability.MAX)  # break it
    assert gear_score(s) == 0  # a broken piece grants nothing until mended


# --- the mend sink ------------------------------------------------------------------------------


def test_repair_session_charges_coins_and_mends():
    s = _engineer_with_wrench()
    equip(s, "wrench")
    durability.wear(s.equipped["weapon"], 20)
    s.coins = 100
    out = durability.repair_session(s)
    assert "mend" in out.lower()
    assert s.coins == 80  # 20 points * 1 coin
    assert durability.current(s.equipped["weapon"]) == durability.MAX


def test_repair_session_refuses_a_short_purse_and_charges_nothing():
    s = _engineer_with_wrench()
    equip(s, "wrench")
    durability.wear(s.equipped["weapon"], 50)
    s.coins = 10  # cannot afford 50
    out = durability.repair_session(s)
    assert "cost" in out.lower()
    assert s.coins == 10  # unchanged
    assert durability.current(s.equipped["weapon"]) == durability.MAX - 50  # not mended


def test_repair_session_on_whole_gear_is_a_clean_noop():
    s = _engineer_with_wrench()
    equip(s, "wrench")
    s.coins = 100
    out = durability.repair_session(s)
    assert "nothing to mend" in out.lower()
    assert s.coins == 100  # no charge


# --- persistence: wear survives the snapshot both gear and bag ride ------------------------------


def test_durability_rides_the_item_snapshot():
    durability.wear("forge_wrench", 25)
    snap = snapshot_item("forge_wrench")
    assert snap is not None and snap["durability"] == durability.MAX - 25
    fresh = reclone_item(snap, items.carrier("clone_owner"))
    assert fresh is not None
    assert durability.current(fresh) == durability.MAX - 25  # wear restored on the clone


def test_a_non_gear_snapshot_carries_no_durability():
    snap = snapshot_item("rusty_lantern")  # not gear (no slot)
    assert snap is not None and "durability" not in snap
