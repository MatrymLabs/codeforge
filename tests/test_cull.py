"""Test twin for parts/world/cull.py -- zone-scoped 'fell N of a kind' contracts at volume.

Acceptance: each zone posts one cull per creature-type of its biome per count-tier, modeled as an
N-step chain that walks to done one kill at a time. Distinctness: a cull listens on `<zone>|<kind>`,
so a kill in one zone never advances another zone's board. Refusal: a biome-less zone posts none.
"""

from __future__ import annotations

from parts.world.bestiary import cullable_types
from parts.world.cull import (
    CULL_PREFIX,
    generate_culls,
    is_cull,
    scope_key,
)

_ZONES = [
    {
        "label": "veridia_wild",
        "name": "The Veridia Wilds",
        "biome": "temperate-meadow",
        "level_max": 30,
    },
    {"label": "frost_wild", "name": "The Frost Wilds", "biome": "glacier-waste", "level_max": 90},
    {"label": "nowhere", "name": "Nowhere", "biome": "", "level_max": 10},  # no biome -> no culls
]


def test_each_zone_posts_a_cull_per_type_per_tier():
    culls = generate_culls(_ZONES)
    assert all(is_cull(q["id"]) for q in culls)
    # each type is a class AND its kin (canid, wolf, hound, jackal, ...); 3 tiers each; void: none
    expected = (len(cullable_types("temperate-meadow")) + len(cullable_types("glacier-waste"))) * 3
    assert len(culls) == expected
    ids = {q["id"] for q in culls}
    assert f"{CULL_PREFIX}veridia_wild_canid_6" in ids, "the class is a target"
    assert f"{CULL_PREFIX}veridia_wild_wolf_6" in ids, "and so is each kin -- a distinct quest"


def test_a_cull_is_an_n_step_chain_that_counts_up():
    cull = next(q for q in generate_culls(_ZONES) if q["id"].endswith("canid_6"))
    assert cull["start"] == "s0" and cull["terminal"] == ["done"]
    assert len(cull["steps"]) == 6, "six kills, six steps -- the state is the tally, no counter"
    assert cull["steps"][-1]["effect"] == "award_xp", "the reward lands on the final kill"
    assert all(s["event"] == "cull" for s in cull["steps"])


def test_every_step_listens_on_the_zone_scoped_key():
    cull = next(q for q in generate_culls(_ZONES) if q["id"].endswith("canid_12"))
    want = scope_key("veridia_wild", "canid")
    assert all(s["on_cull"] == want for s in cull["steps"])
    assert want == "veridia_wild|canid", "the scope key is <zone>|<kind>"


def test_kills_in_one_zone_do_not_advance_another_zones_cull():
    # the two zones' canid culls listen on DIFFERENT keys, so their boards never cross
    culls = {q["id"]: q for q in generate_culls(_ZONES)}
    veridia = culls[f"{CULL_PREFIX}veridia_wild_canid_6"]["steps"][0]["on_cull"]
    frost = culls[f"{CULL_PREFIX}frost_wild_canid_6"]["steps"][0]["on_cull"]
    assert veridia != frost


def test_a_biomeless_zone_posts_nothing_and_forging_is_deterministic():
    assert generate_culls([{"label": "x", "name": "X", "biome": ""}]) == []
    assert generate_culls(_ZONES) == generate_culls(_ZONES)


def test_the_board_reads_varied_not_a_thousand_clones():
    # The mechanic is fixed, but presentation must vary: across a zone's kinds the contract framings
    # differ (not all "Cull the X"), tiers get distinct words, and the close is region-toned.
    from parts.world.cull import generate_culls

    culls = generate_culls(_ZONES)
    # name reads "<tier-phrase> <framing>: the <kind>-kind of <zone>", e.g. "A great Purge: ...".
    framings = {c["name"].split(":")[0].split(" ")[-1] for c in culls}  # the framing word
    assert len(framings) >= 2, "the board should not read as one framing repeated"
    tiers = {" ".join(c["name"].split(" ")[:2]) for c in culls}  # the two-word tier phrase
    assert {"A small", "A standing", "A great"} <= tiers
    # a Veridia (temperate-meadow) cull's completion carries the region's tone
    veridia = next(c for c in culls if c["id"].startswith("cull_veridia_wild_"))
    assert "farm-roads" in veridia["labels"]["done"]


def test_the_flavour_is_deterministic():
    from parts.world.cull import generate_culls

    a = {(c["id"], c["name"]) for c in generate_culls(_ZONES)}
    b = {(c["id"], c["name"]) for c in generate_culls(_ZONES)}
    assert a == b  # same board, same faces, every boot
