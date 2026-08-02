"""Conformance twin for the aethryn REFINEMENT CHAINS (Crafting Campaign, slice 1a).

Slice 1a adds the material library as data: the missing middle tiers RAW -> REFINED -> COMPONENT
-> PRODUCT, expressed as chained recipes in seeds/aethryn/recipes.yaml over materials in
items.yaml. crafting.py itself is unchanged, so these tests pin the DATA, not new code:

Acceptance -- every chain link resolves (its inputs and output are real seed items, and each
non-terminal tier is consumed by the next), and a maker can craft a whole chain end to end,
consuming each tier to mint the next. Refusal -- a refined step with only the raw tier in hand
fails loud and spends nothing (you cannot skip the refinement).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.world import crafting, items
from kernel.world.seed import load_items, load_professions, load_recipes
from kernel.world.session import Session

_AETHRYN = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"

# The two exemplar chains slice 1a ships, lowest tier first. Each is (base_material, *steps) where a
# step is (recipe_label, output_prototype). A step's output must be an input of the next step, and
# the final output is the terminal product.
_CHAINS = {
    "metal": [
        ("smelt_wrought_ingot", "wrought_ingot"),
        ("forge_iron_fitting", "iron_fitting"),
        ("assemble_travelers_buckler", "travelers_buckler"),
    ],
    "alchemy": [
        ("distil_meadowfoil_reagent", "herbal_reagent"),
        ("brew_restorative_tonic", "restorative_tonic"),
    ],
    # Slice 1c: the monster-material chains, rooted in bestiary drops (raw_hide / chitin_scale).
    "hide": [
        ("tan_leather", "cured_leather"),
        ("stitch_hide_jerkin", "hide_jerkin"),
    ],
    "scale": [
        ("harden_scale", "hardened_scale"),
        ("forge_scale_bracer", "scale_bracer"),
    ],
}


@pytest.fixture
def aethryn():
    """Load aethryn's items + recipes into the registries so the chains can actually be crafted.
    Snapshot-and-restore both globals so this leaks nothing into other tests."""
    proto_snap = dict(items.PROTOTYPES)
    items_snap = dict(items.ITEMS)
    protos = load_items(_AETHRYN / "items.yaml")
    items.register_prototypes(protos)
    recipes = load_recipes(_AETHRYN / "recipes.yaml")
    yield {"recipes": recipes, "protos": protos}
    items.PROTOTYPES.clear()
    items.PROTOTYPES.update(proto_snap)
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)


def _player() -> Session:
    return Session(player_id="maker", location="courtyard")


def test_every_refinement_link_references_a_real_item(aethryn):
    """No chain link may make or need a material that isn't a real seed item (the loader gates this
    at boot; this pins it against silent drift when someone edits the yaml)."""
    recipes, protos = aethryn["recipes"], aethryn["protos"]
    for name, steps in _CHAINS.items():
        for label, output in steps:
            recipe = recipes.get(label)
            assert recipe is not None, f"{name} chain: recipe '{label}' is missing"
            assert recipe["makes"] == output, f"{label} should make {output}"
            assert output in protos, f"{label} makes '{output}', not a real item"
            for proto in recipe["inputs"]:
                assert proto in protos, f"{label} needs '{proto}', not a real item"


def test_every_recipe_gate_names_a_real_trade_and_order(aethryn):
    """A gated recipe (slice 1d) must require a real CRAFT profession and/or a real Order, else a
    maker could never earn it."""
    from kernel.world.orders import ORDERS

    profs = load_professions(_AETHRYN / "professions.yaml")
    craft_trades = {p for p in profs if profs[p]["kind"] == "craft"}
    for label, recipe in aethryn["recipes"].items():
        gate = recipe.get("requires")
        if not gate:
            continue
        if "profession" in gate:
            assert gate["profession"] in craft_trades, f"{label} gate names bad trade"
        if "order" in gate:
            assert gate["order"] in ORDERS, f"{label} gate names unknown Order"


def test_at_least_one_recipe_is_gated_so_the_system_is_live(aethryn):
    assert any(r.get("requires") for r in aethryn["recipes"].values()), "1d gating is dormant"


def test_each_tier_feeds_the_next(aethryn):
    """A chain is only a chain if each refined tier is consumed by the following step -- otherwise
    it is two disconnected recipes, not a RAW -> REFINED -> PRODUCT climb."""
    recipes = aethryn["recipes"]
    for name, steps in _CHAINS.items():
        for (label, output), (next_label, _) in zip(steps, steps[1:], strict=False):
            assert output in recipes[next_label]["inputs"], (
                f"{name} chain break: {label} makes {output}, but {next_label} does not use it"
            )


@pytest.mark.parametrize("chain", list(_CHAINS))
def test_a_maker_can_craft_a_whole_chain_end_to_end(monkeypatch, aethryn, chain):
    """Feed the base material, then craft each step; every tier is consumed to mint the next and the
    terminal product ends up in hand."""
    monkeypatch.setattr(crafting, "RECIPES", aethryn["recipes"])
    steps = _CHAINS[chain]
    # Stock enough of the FIRST recipe's inputs (its raw materials) to run step one.
    for proto, qty in aethryn["recipes"][steps[0][0]]["inputs"].items():
        for _ in range(qty):
            items.clone(proto, items.carrier("maker"))
    s = _player()
    for label, output in steps:
        # top up any extra ingredient a step needs beyond the prior tier (e.g. ember_shard)
        for proto, qty in aethryn["recipes"][label]["inputs"].items():
            while len(crafting._held(proto, items.carrier("maker"))) < qty:
                items.clone(proto, items.carrier("maker"))
        out = crafting.craft(s, label)
        assert "forge" in out.lower(), f"{chain}:{label} did not craft: {out}"
        assert len(crafting._held(output, items.carrier("maker"))) >= 1, (
            f"{chain}:{label} minted no {output}"
        )
    product = steps[-1][1]
    assert len(crafting._held(product, items.carrier("maker"))) == 1, (
        f"{chain} did not yield its product {product}"
    )


def test_a_refined_step_refuses_the_raw_tier_and_spends_nothing(monkeypatch, aethryn):
    """You cannot skip refinement: brewing the tonic with only herbs (no reagent) fails loud and
    consumes nothing -- the raw tier stays in your hands."""
    monkeypatch.setattr(crafting, "RECIPES", aethryn["recipes"])
    s = _player()
    items.clone(
        "meadowfoil", items.carrier("maker")
    )  # a raw herb, but the tonic needs the refined reagent
    items.clone("meadowfoil", items.carrier("maker"))
    out = crafting.craft(s, "brew_restorative_tonic")
    assert "lack materials" in out.lower() and "herbal_reagent" in out
    assert len(crafting._held("meadowfoil", items.carrier("maker"))) == 2  # nothing spent
    assert len(crafting._held("restorative_tonic", items.carrier("maker"))) == 0  # nothing made
