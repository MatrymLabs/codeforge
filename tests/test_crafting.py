"""Test twin for parts/world/crafting.py -- the maker's loop: `craft <recipe>`.

Acceptance: a recipe consumes its material inputs from the inventory and mints its output; a bare
`craft` lists what you can make; the verb is reachable through the engine tick. Refusal: an unknown
recipe and missing materials both fail loud and spend NOTHING. Recipes are injected (monkeypatched)
so the test does not depend on a seed shipping one.
"""

from __future__ import annotations

import pytest

from parts.world import crafting, items
from parts.world.session import Session

# A recipe over first-forge items (the test seed): two forge wrenches make a healing draught.
_RECIPES = {
    "testmake": {
        "name": "a healing draught",
        "makes": "healing_draught",
        "inputs": {"forge_wrench": 2},
    },
}


@pytest.fixture(autouse=True)
def fresh_items():
    # ITEMS is a module global conftest does not reset; snapshot so cloning to "player" never leaks.
    snap = dict(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snap)


def _player() -> Session:
    return Session(player_id="maker", location="courtyard")


def test_craft_consumes_inputs_and_mints_the_output(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    s = _player()
    items.clone("forge_wrench", "player")
    items.clone("forge_wrench", "player")
    out = crafting.craft(s, "testmake")
    assert "forge" in out.lower() and "healing draught" in out.lower()
    assert len(crafting._held("healing_draught")) == 1  # one made
    assert len(crafting._held("forge_wrench")) == 0  # both spent


def test_craft_refuses_an_unknown_recipe(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    assert "no recipe" in crafting.craft(_player(), "nonsense").lower()


def test_craft_without_materials_refuses_and_spends_nothing(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    s = _player()
    items.clone("forge_wrench", "player")  # only one, the recipe needs two
    out = crafting.craft(s, "testmake")
    assert "lack materials" in out.lower() and "1 more forge_wrench" in out
    assert len(crafting._held("forge_wrench")) == 1  # nothing spent
    assert len(crafting._held("healing_draught")) == 0  # nothing made


def test_bare_craft_lists_the_recipes(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    out = crafting.craft(_player(), "")
    assert "You can forge" in out and "testmake" in out and "2x forge_wrench" in out


def test_craft_with_no_recipes_says_there_is_nothing_to_craft(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", {})
    assert "nothing to craft" in crafting.craft(_player(), "").lower()


def test_craft_fails_gracefully_when_the_output_is_unknown(monkeypatch):
    """A recipe whose output isn't a real item fails cleanly and spends nothing (the output is
    minted before inputs are consumed, so a bad recipe never eats your materials)."""
    bad = {"bad": {"name": "a phantom", "makes": "no_such_item", "inputs": {"forge_wrench": 1}}}
    monkeypatch.setattr(crafting, "RECIPES", bad)
    s = _player()
    items.clone("forge_wrench", "player")
    out = crafting.craft(s, "bad")
    assert "cannot forge" in out.lower()
    assert len(crafting._held("forge_wrench")) == 1  # materials untouched on a failed craft


def test_craft_is_reachable_through_the_engine_tick(monkeypatch):
    import forge

    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    out = forge.handle_command(Session(player_id="maker", location="courtyard"), "craft")
    assert "You can forge" in out  # the verb is wired into the tick
