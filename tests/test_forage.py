"""Test twin for parts/world/forage.py -- zone-scoped 'gather N of a material' contracts.

Acceptance: each zone posts one forage per material its biome yields per count-tier, an N-step chain
that walks to done one harvest at a time. Distinctness: it listens on `<zone>|<mat>`, the same scope
the gather action fires, so a harvest in one zone never fills another. Refusal: no biome, no forage.
"""

from __future__ import annotations

from parts.world.cull import scope_key
from parts.world.forage import FORAGE_PREFIX, generate_forages, is_forage

_ZONES = [
    # temperate meadow yields ember_shard only; glacier-waste is an ore biome (+ hollow_ingot)
    {
        "label": "veridia_wild",
        "name": "The Veridia Wilds",
        "biome": "temperate-meadow",
        "level_max": 30,
    },
    {"label": "frost_wild", "name": "The Frost Wilds", "biome": "glacier-waste", "level_max": 90},
    {"label": "void", "name": "Void", "biome": "", "level_max": 10},  # no biome -> none
]


def test_each_zone_posts_a_forage_per_material_per_tier():
    from parts.world.wildlands import gatherable_materials

    forages = generate_forages(_ZONES)
    assert all(is_forage(q["id"]) for q in forages)
    # one forage per (material its biome yields) x 2 tiers, for the two biome zones (void: none)
    expected = (
        len(gatherable_materials("temperate-meadow")) + len(gatherable_materials("glacier-waste"))
    ) * 2
    assert len(forages) == expected
    ids = {q["id"] for q in forages}
    assert f"{FORAGE_PREFIX}frost_wild_hollow_ingot_5" in ids, "an ore zone forages the ingot too"


def test_a_forage_is_an_n_step_chain_scoped_to_the_zone_material():
    forage = next(q for q in generate_forages(_ZONES) if q["id"].endswith("ember_shard_5"))
    assert forage["start"] == "s0" and forage["terminal"] == ["done"]
    assert len(forage["steps"]) == 5, "five harvests, five steps -- the state is the tally"
    assert forage["steps"][-1]["effect"] == "award_xp"
    want = scope_key("veridia_wild", "ember_shard")
    assert all(s["on_forage"] == want and s["event"] == "forage" for s in forage["steps"])


def test_harvests_in_one_zone_do_not_fill_another():
    forages = {q["id"]: q for q in generate_forages(_ZONES)}
    a = forages[f"{FORAGE_PREFIX}veridia_wild_ember_shard_5"]["steps"][0]["on_forage"]
    b = forages[f"{FORAGE_PREFIX}frost_wild_ember_shard_5"]["steps"][0]["on_forage"]
    assert a != b


def test_a_biomeless_zone_posts_nothing_and_forging_is_deterministic():
    assert generate_forages([{"label": "x", "name": "X", "biome": ""}]) == []
    assert generate_forages(_ZONES) == generate_forages(_ZONES)


def test_the_forage_board_reads_varied():
    from parts.world.forage import generate_forages

    forages = generate_forages(_ZONES)
    framings = {f["name"].split(":")[0].split(" ")[-1] for f in forages}
    assert len(framings) >= 2, "the forage board should not read as one framing repeated"
    tiers = {" ".join(f["name"].split(" ")[:2]) for f in forages}
    assert {"A small", "A standing"} <= tiers
    veridia = next(f for f in forages if f["id"].startswith("forage_veridia_wild_"))
    assert "makers" in veridia["labels"]["done"]  # region-toned close


def test_the_forage_flavour_is_deterministic():
    from parts.world.forage import generate_forages

    a = {(f["id"], f["name"]) for f in generate_forages(_ZONES)}
    b = {(f["id"], f["name"]) for f in generate_forages(_ZONES)}
    assert a == b
