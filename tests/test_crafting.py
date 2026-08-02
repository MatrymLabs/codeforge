"""Test twin for kernel/world/crafting.py -- the maker's loop: `craft <recipe>`.

Acceptance: a recipe consumes its material inputs from the inventory and mints its output; a bare
`craft` lists what you can make; the verb is reachable through the engine tick. Refusal: an unknown
recipe and missing materials both fail loud and spend NOTHING. Recipes are injected (monkeypatched)
so the test does not depend on a seed shipping one.
"""

from __future__ import annotations

import pytest

from kernel.world import crafting, items
from kernel.world.session import Session

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
    items.clone("forge_wrench", items.carrier("maker"))
    items.clone("forge_wrench", items.carrier("maker"))
    out = crafting.craft(s, "testmake")
    assert "forge" in out.lower() and "healing draught" in out.lower()
    assert len(crafting._held("healing_draught", items.carrier("maker"))) == 1  # one made
    assert len(crafting._held("forge_wrench", items.carrier("maker"))) == 0  # both spent


def test_craft_refuses_an_unknown_recipe(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    assert "no recipe" in crafting.craft(_player(), "nonsense").lower()


def test_craft_without_materials_refuses_and_spends_nothing(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    s = _player()
    items.clone("forge_wrench", items.carrier("maker"))  # only one, the recipe needs two
    out = crafting.craft(s, "testmake")
    assert "lack materials" in out.lower() and "1 more forge_wrench" in out
    assert len(crafting._held("forge_wrench", items.carrier("maker"))) == 1  # nothing spent
    assert len(crafting._held("healing_draught", items.carrier("maker"))) == 0  # nothing made


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
    items.clone("forge_wrench", items.carrier("maker"))
    out = crafting.craft(s, "bad")
    assert "cannot forge" in out.lower()
    assert (
        len(crafting._held("forge_wrench", items.carrier("maker"))) == 1
    )  # materials untouched on a failed craft


def test_craft_is_reachable_through_the_engine_tick(monkeypatch):
    import forge

    monkeypatch.setattr(crafting, "RECIPES", _RECIPES)
    out = forge.handle_command(Session(player_id="maker", location="courtyard"), "craft")
    assert "You can forge" in out  # the verb is wired into the tick


# --- Recipe acquisition gates (slice 1d): a recipe earned by profession level and/or a sworn Order.

_GATED = {
    "mastercraft": {
        "name": "a mastercraft draught",
        "makes": "healing_draught",
        "inputs": {"forge_wrench": 1},
        "requires": {"profession": "alchemy", "level": 3},
    },
}
# The test seed ships no professions, so patch a trade in for the gate's display name to resolve.
_ALCHEMY = {"alchemy": {"name": "Alchemy", "kind": "craft", "works": [], "makes": []}}


def test_an_open_recipe_has_no_lock():
    assert crafting.locked_reason(_player(), _RECIPES["testmake"]) is None


def test_a_gated_recipe_is_locked_until_the_profession_level(monkeypatch):
    from kernel.world import professions

    monkeypatch.setattr(professions, "PROFESSIONS", _ALCHEMY)
    monkeypatch.setattr(crafting, "RECIPES", _GATED)
    s = _player()
    items.clone("forge_wrench", items.carrier("maker"))
    # Under the required level: locked, craft refuses, and nothing is spent.
    assert "needs Alchemy level 3" in crafting.locked_reason(s, _GATED["mastercraft"])
    out = crafting.craft(s, "mastercraft")
    assert "have not earned" in out.lower()
    assert (
        len(crafting._held("forge_wrench", items.carrier("maker"))) == 1
    )  # refused, nothing spent
    # Practise the trade to level 3 (PER_LEVEL per rank) and the gate opens.
    s.professions["alchemy"] = professions.PER_LEVEL * 2  # level 3
    assert crafting.locked_reason(s, _GATED["mastercraft"]) is None
    assert "forge" in crafting.craft(s, "mastercraft").lower()


def test_an_order_gated_recipe_needs_the_sworn_order():
    recipe = {
        "name": "a guild relic",
        "makes": "x",
        "inputs": {"y": 1},
        "requires": {"order": "making"},
    }
    unsworn = Session(player_id="m", location="void")  # order == ""
    assert "needs the" in crafting.locked_reason(unsworn, recipe)
    sworn = Session(player_id="m", location="void")
    sworn.order = "making"
    assert crafting.locked_reason(sworn, recipe) is None


def test_the_recipe_sheet_marks_a_locked_recipe(monkeypatch):
    from kernel.world import professions

    monkeypatch.setattr(professions, "PROFESSIONS", _ALCHEMY)
    monkeypatch.setattr(crafting, "RECIPES", _GATED)
    sheet = crafting.render_recipes(_player())
    assert "[locked: needs Alchemy level 3]" in sheet


def test_load_recipes_accepts_a_valid_gate(tmp_path):
    from kernel.world.seed import load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n"
        "  requires: {profession: smithing, level: 2, order: making}\n",
        encoding="utf-8",
    )
    assert load_recipes(p)["r"]["requires"] == {
        "profession": "smithing",
        "level": 2,
        "order": "making",
    }


def test_load_recipes_rejects_an_unknown_gate_key(tmp_path):
    from kernel.world.seed import SeedError, load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text("r:\n  makes: x\n  inputs: {y: 1}\n  requires: {level_up: 3}\n", encoding="utf-8")
    with pytest.raises(SeedError, match="requires"):
        load_recipes(p)


def test_load_recipes_rejects_a_profession_gate_without_a_positive_level(tmp_path):
    from kernel.world.seed import SeedError, load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n  requires: {profession: smithing}\n", encoding="utf-8"
    )
    with pytest.raises(SeedError, match="level"):
        load_recipes(p)


def test_load_recipes_rejects_a_non_string_profession(tmp_path):
    from kernel.world.seed import SeedError, load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n  requires: {profession: 7, level: 2}\n",
        encoding="utf-8",
    )
    with pytest.raises(SeedError, match="profession"):
        load_recipes(p)


def test_load_recipes_rejects_a_non_string_order(tmp_path):
    from kernel.world.seed import SeedError, load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text("r:\n  makes: x\n  inputs: {y: 1}\n  requires: {order: 3}\n", encoding="utf-8")
    with pytest.raises(SeedError, match="Order"):
        load_recipes(p)


def test_load_recipes_accepts_an_order_only_gate(tmp_path):
    from kernel.world.seed import load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n  requires: {order: making}\n", encoding="utf-8"
    )
    assert load_recipes(p)["r"]["requires"] == {"order": "making"}


# --- reputation-standing gate on a recipe (roadmap #2: faction-gated content) ------------------
_STANDING_GATED = {
    "guildwork": {
        "name": "a guild relic",
        "makes": "healing_draught",
        "inputs": {"forge_wrench": 1},
        "requires": {"order": "making", "standing": 300},
    },
}


def test_a_standing_gate_needs_the_sworn_order_first(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _STANDING_GATED)
    unsworn = _player()  # order == ""
    assert "needs the" in crafting.locked_reason(unsworn, _STANDING_GATED["guildwork"])


def test_a_standing_gate_needs_the_reputation_tier(monkeypatch):
    monkeypatch.setattr(crafting, "RECIPES", _STANDING_GATED)
    s = _player()
    s.order = "making"  # sworn, but standing 0 (< 300)
    locked = crafting.locked_reason(s, _STANDING_GATED["guildwork"])
    assert locked is not None and "standing" in locked.lower() and "Honored" in locked
    s.reputation["making"] = 300  # now Honored
    assert crafting.locked_reason(s, _STANDING_GATED["guildwork"]) is None


def test_load_recipes_accepts_a_standing_gate(tmp_path):
    from kernel.world.seed import load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n  requires: {order: making, standing: 300}\n",
        encoding="utf-8",
    )
    assert load_recipes(p)["r"]["requires"] == {"order": "making", "standing": 300}


def test_load_recipes_rejects_a_standing_without_an_order(tmp_path):
    from kernel.world.seed import SeedError, load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n  requires: {standing: 300}\n", encoding="utf-8"
    )
    with pytest.raises(SeedError, match="standing"):
        load_recipes(p)


def test_load_recipes_rejects_a_non_positive_standing(tmp_path):
    from kernel.world.seed import SeedError, load_recipes

    p = tmp_path / "recipes.yaml"
    p.write_text(
        "r:\n  makes: x\n  inputs: {y: 1}\n  requires: {order: making, standing: 0}\n",
        encoding="utf-8",
    )
    with pytest.raises(SeedError, match="standing"):
        load_recipes(p)
