"""Test twin for kernel/world/travel.py -- the Waystone network (the economy's coin sink).

Acceptance: at a waystone, `travel` lists the network + level-scaled fares, and `travel <where>`
pays the fare and carries you. Refusal: off a waystone, an unknown/same hub, and an empty purse all
fail cleanly. Load: the shipped manifest is valid; the fare climbs with the destination band.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from kernel.world import travel as tv
from kernel.world.seed import BlueprintError
from kernel.world.session import Session

_STONES = {
    "veridia": {"name": "Veridia", "level": 1},
    "duskwood": {"name": "Duskwood Vale", "level": 20},
    "voidscar": {"name": "The Voidscar", "level": 250},
}


def _at(hub: str, coins: int = 1000) -> Session:
    return Session(player_id="wanderer", location=hub, coins=coins)


def test_the_fare_climbs_with_the_destination_band():
    assert tv.fare(1) < tv.fare(20) < tv.fare(250)  # a deep hop costs a fortune


def test_the_bare_verb_lists_the_network_and_fares():
    out = tv.travel(_at("veridia"), "", _STONES)
    assert "Veridia waystone hums" in out and "Duskwood Vale" in out and "The Voidscar" in out
    assert "travel <where>" in out.lower()


def test_travelling_pays_the_fare_and_carries_you():
    s = _at("veridia", coins=1000)
    out = tv.travel(s, "duskwood", _STONES)
    assert "carried to the Duskwood Vale" in out
    assert s.location == "duskwood" and s.coins == 1000 - tv.fare(20)  # coins sank


def test_an_empty_purse_is_refused_and_you_do_not_move():
    s = _at("veridia", coins=5)
    out = tv.travel(s, "voidscar", _STONES)
    assert "demands" in out and s.location == "veridia" and s.coins == 5


def test_off_a_waystone_and_bad_or_same_hub_fail_cleanly():
    assert "no waystone here" in tv.travel(_at("some_field"), "", _STONES)
    assert "knows no waystone" in tv.travel(_at("veridia"), "atlantis", _STONES)
    assert "already at" in tv.travel(_at("veridia"), "veridia", _STONES)


def test_load_waystones_reads_the_shipped_manifest():
    aethryn = Path(__file__).resolve().parent.parent / "content" / "blueprints" / "aethryn"
    stones = tv.load_waystones(aethryn / "waystones.yaml")
    assert stones and len(stones) == 14  # the 14 zone hubs
    assert all("name" in s and 1 <= s["level"] <= 300 for s in stones.values())


@pytest.mark.parametrize(
    "bad, match",
    [
        ({"name": "X"}, "needs a 'name' and a 'level'"),
        ({"name": "X", "level": 0}, "'level' must be an int"),
    ],
)
def test_a_malformed_waystone_fails_loud(bad, match):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "waystones.yaml"
        p.write_text(yaml.safe_dump({"hub": bad}))
        with pytest.raises(BlueprintError, match=match):
            tv.load_waystones(p)
