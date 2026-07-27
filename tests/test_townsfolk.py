"""Test twin for parts/world/townsfolk.py -- settlements grow residents + a merchant (the sink).

Acceptance: a settlement config grows a crowd of peaceful townsfolk (each a trade with a topic) plus
one merchant whose shop stocks level-appropriate, real seed consumables. Refusal: a malformed
settlement fails loud. Load: the shipped aethryn manifest is valid data.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from parts.world.seed import SeedError
from parts.world.townsfolk import (
    _FOLK_PER_TOWN,
    load_settlements,
    make_merchant,
    populate_settlements,
)

_CFG = [{"room": "greenhold", "name": "Greenhold", "zone": "Veridia", "level": 1}]
# The default test seed is first-forge; these tests exercise the flagship map, so reach it directly.
_AETHRYN = Path(__file__).resolve().parent.parent / "seeds" / "aethryn"


def test_a_settlement_grows_folk_and_exactly_one_merchant():
    npcs = populate_settlements(_CFG)
    folk = [n for k, n in npcs.items() if "_dweller_" in k]
    merchants = [n for k, n in npcs.items() if k.endswith("_merchant")]
    assert len(folk) == _FOLK_PER_TOWN and len(merchants) == 1
    for n in folk:
        assert n["hp"] == 0 and n["atk"] == 0  # townsfolk are never a fight
        assert n["location"] == "greenhold" and n["topics"]  # they live here and have a word to say


def test_the_merchant_sells_level_appropriate_real_consumables():
    _, low = make_merchant(1, "greenhold", "Greenhold")
    _, high = make_merchant(120, "zulkarak", "Zulkarak")
    assert "healing_draught" in low["shop"]["sells"]  # a starter town sells basic draughts
    assert "grand_healing_draught" in high["shop"]["sells"]  # a deep town sells grand ones
    # the merchant buys its own wares back (a coin source for spares), at less than it sells
    for proto, price in low["shop"]["sells"].items():
        assert 0 < low["shop"]["buys"][proto] <= price
    assert low["hp"] == 0  # a merchant is peaceful too


def test_the_merchant_wares_are_all_real_seed_prototypes():
    # every draught a merchant stocks must be a real aethryn item, or the boot cross-check fails.
    from parts.world.seed import load_items

    items = load_items(_AETHRYN / "items.yaml")
    _, merchant = make_merchant(200, "zulkarak", "Zulkarak")
    for proto in {**merchant["shop"]["sells"], **merchant["shop"]["buys"]}:
        assert proto in items, f"merchant stocks a non-existent item {proto!r}"


def test_load_settlements_reads_the_shipped_manifest():
    configs = load_settlements(_AETHRYN / "settlements.yaml")
    assert configs and all({"room", "name", "zone", "level"} <= set(c) for c in configs)
    assert all(1 <= c["level"] <= 300 for c in configs)


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"name": "X", "zone": "Z"}, "missing required key 'level'"),
        ({"name": "X", "zone": "Z", "level": 0}, "'level' must be an int"),
        ({"name": "X", "zone": "Z", "level": 999}, "'level' must be an int"),
    ],
)
def test_a_malformed_settlement_fails_loud(bad, match):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "settlements.yaml"
        p.write_text(yaml.safe_dump({"town": bad}))
        with pytest.raises(SeedError, match=match):
            load_settlements(p)
