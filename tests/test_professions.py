"""Test twin for parts/world/professions.py -- the maker's trades (Crafting Campaign, slice 1b).

Two layers. CONFORMANCE pins the aethryn trade data as coherent: every material a gather trade works
and every recipe a craft trade makes is real, every recipe belongs to exactly one craft trade, and
every gatherable material to a gather trade -- so nothing a maker does goes unclaimed. FUNCTIONAL
pins the framework over a small synthetic trade set (the active test seed ships no professions):
the skill curve, awarding practice, the rank-up line, gather/craft wiring, the sheet, persistence
round-trip, and engine-tick reachability. Acceptance AND refusal (a None/unknown trade is a no-op).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import forge
from parts.world import crafting, items, professions
from parts.world.seed import load_items, load_professions, load_recipes
from parts.world.session import SESSIONS, Session
from parts.world.world import WORLD

_AETHRYN = Path(__file__).resolve().parent.parent / "seeds" / "aethryn"


# --- CONFORMANCE: the aethryn trade data is real and complete -------------------------------------


@pytest.fixture(scope="module")
def aethryn():
    profs = load_professions(_AETHRYN / "professions.yaml")
    protos = load_items(_AETHRYN / "items.yaml")
    recipes = load_recipes(_AETHRYN / "recipes.yaml")
    return {"profs": profs, "protos": protos, "recipes": recipes}


def test_every_gather_trade_works_only_real_materials(aethryn):
    for pid, prof in aethryn["profs"].items():
        if prof["kind"] == "gather":
            for mat in prof["works"]:
                assert mat in aethryn["protos"], f"{pid} works '{mat}', not a real item"


def test_every_craft_trade_makes_only_real_recipes(aethryn):
    for pid, prof in aethryn["profs"].items():
        if prof["kind"] == "craft":
            for label in prof["makes"]:
                assert label in aethryn["recipes"], f"{pid} makes '{label}', not a real recipe"


def test_every_recipe_belongs_to_exactly_one_craft_trade(aethryn):
    """No recipe may be orphaned (crafting it would earn no trade) or claimed twice."""
    claims: dict[str, list[str]] = {label: [] for label in aethryn["recipes"]}
    for pid, prof in aethryn["profs"].items():
        if prof["kind"] == "craft":
            for label in prof["makes"]:
                claims.setdefault(label, []).append(pid)
    orphans = [label for label, owners in claims.items() if not owners]
    dupes = {label: owners for label, owners in claims.items() if len(owners) > 1}
    assert not orphans, f"recipes claimed by no craft trade: {orphans}"
    assert not dupes, f"recipes claimed by more than one trade: {dupes}"


def test_every_gatherable_material_belongs_to_a_gather_trade(aethryn):
    """Every material the wildlands can seed as a node must be claimed by a gather trade, or working
    it earns nothing."""
    from parts.world.wildlands import _BIOMES, gatherable_materials

    gatherable = {m for biome in _BIOMES for m in gatherable_materials(biome)}
    worked = {m for p in aethryn["profs"].values() if p["kind"] == "gather" for m in p["works"]}
    assert gatherable <= worked, f"gatherable materials no trade works: {gatherable - worked}"


# --- FUNCTIONAL: the framework over a synthetic trade set -----------------------------------------

_TRADES = {
    "testmine": {"name": "Testmine", "kind": "gather", "works": ["forge_wrench"], "makes": []},
    "testsmith": {"name": "Testsmith", "kind": "craft", "works": [], "makes": ["testmake"]},
}
_RECIPE = {
    "testmake": {
        "name": "a healing draught",
        "makes": "healing_draught",
        "inputs": {"forge_wrench": 2},
    }
}


@pytest.fixture
def synthetic(monkeypatch):
    """Patch the trade registry + reverse lookups + recipes to a tiny, deterministic set."""
    monkeypatch.setattr(professions, "PROFESSIONS", _TRADES)
    monkeypatch.setattr(professions, "GATHER_OF", {"forge_wrench": "testmine"})
    monkeypatch.setattr(professions, "CRAFT_OF", {"testmake": "testsmith"})
    monkeypatch.setattr(crafting, "RECIPES", _RECIPE)
    SESSIONS.clear()
    WORLD["probe_node_room"] = {"name": "Seam", "desc": "ore", "exits": {}, "node": "forge_wrench"}
    yield
    WORLD.pop("probe_node_room", None)
    for iid in [i for i in items.ITEMS if items.is_clone(i)]:
        del items.ITEMS[iid]
    SESSIONS.clear()


def test_level_for_climbs_one_rank_per_threshold_and_caps():
    assert professions.level_for(0) == 1
    assert professions.level_for(professions.PER_LEVEL - 1) == 1
    assert professions.level_for(professions.PER_LEVEL) == 2
    assert professions.level_for(professions.PER_LEVEL * 999) == professions.LEVEL_CAP


def test_advance_earns_practice_and_announces_only_on_rank_up(synthetic):
    s = Session(player_id="maker", location="void")
    assert professions.advance(s, "testmine") is None  # practice 1, still level 1: silent
    assert s.professions["testmine"] == 1
    for _ in range(professions.PER_LEVEL - 2):
        professions.advance(s, "testmine")
    line = professions.advance(s, "testmine")  # the PER_LEVEL-th unit -> level 2
    assert line is not None and "level 2" in line and "Testmine" in line


def test_advance_is_a_no_op_for_a_none_or_unknown_trade(synthetic):
    s = Session(player_id="maker", location="void")
    assert professions.advance(s, None) is None
    assert professions.advance(s, "no_such_trade") is None
    assert s.professions == {}  # nothing awarded


def test_gathering_earns_the_gather_trade(synthetic):
    s = Session(player_id="forager", location="probe_node_room")
    SESSIONS["forager"] = s
    forge.handle_command(s, "gather")
    assert s.professions.get("testmine") == 1  # working forge_wrench earned Testmine


def test_crafting_earns_the_craft_trade(synthetic):
    s = Session(player_id="smith", location="void")
    items.clone("forge_wrench", "player")
    items.clone("forge_wrench", "player")
    out = crafting.craft(s, "testmake")
    assert "forge" in out.lower()
    assert s.professions.get("testsmith") == 1  # forging testmake earned Testsmith


def test_the_sheet_lists_gather_and_craft_trades_with_levels(synthetic):
    s = Session(player_id="maker", location="void")
    s.professions["testmine"] = professions.PER_LEVEL  # level 2
    sheet = professions.render_professions(s)
    assert "Gathering" in sheet and "Crafting" in sheet
    assert "Testmine -- level 2" in sheet and "Testsmith -- level 1" in sheet


def test_professions_persist_round_trip(synthetic):
    s = Session(player_id="maker", location="void")
    s.professions = {"testmine": 7, "testsmith": 3}
    blob = professions.serialize(s)
    restored = Session(player_id="maker", location="void")
    professions.restore(restored, blob)
    assert restored.professions == {"testmine": 7, "testsmith": 3}


def test_restore_drops_unknown_or_malformed_trades(synthetic):
    s = Session(player_id="maker", location="void")
    professions.restore(s, "testmine:4,gone_trade:9,junk,testsmith:notanumber")
    assert s.professions == {"testmine": 4}  # only the real, well-formed pair survives


def test_professions_verb_is_reachable_through_the_tick(synthetic):
    out = forge.handle_command(Session(player_id="maker", location="void"), "professions")
    assert "Your trades" in out
