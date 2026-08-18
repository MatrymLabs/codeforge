"""Test twin for kernel/world/delivery.py -- 'carry a parcel from town A to town B' contracts.

Acceptance: each settlement consigns a parcel to its level-adjacent trade-partner; the quest is a
two-beat arc (take the parcel, then arrive at the destination) and the generator mints the parcel
item at the source. Refusal: fewer than two settlements route nothing. Determinism holds.
"""

from __future__ import annotations

from kernel.world.delivery import (
    DELIVERY_PREFIX,
    PARCEL_PREFIX,
    generate_deliveries,
    is_delivery,
)

_TOWNS = [
    {"room": "greenhold", "name": "Greenhold", "level": 1},
    {"room": "elderwatch", "name": "Elderwatch", "level": 5},
    {"room": "moltenhold", "name": "Moltenhold", "level": 120},
]


def test_one_delivery_per_town_to_its_level_neighbour():
    specs, parcels = generate_deliveries(_TOWNS)  # noqa: RUF059
    assert len(specs) == len(_TOWNS) and all(is_delivery(s["id"]) for s in specs)
    # sorted by level: greenhold(1) -> elderwatch(5) -> moltenhold(120) -> greenhold (wrap)
    routes = {s["id"]: s["name"] for s in specs}
    assert routes[f"{DELIVERY_PREFIX}greenhold"] == "Delivery: Greenhold to Elderwatch"
    assert routes[f"{DELIVERY_PREFIX}moltenhold"] == "Delivery: Moltenhold to Greenhold", "wraps"


def test_the_arc_is_take_then_arrive_with_the_reward_on_delivery():
    specs, parcels = generate_deliveries(_TOWNS)  # noqa: RUF059
    spec = next(s for s in specs if s["id"] == f"{DELIVERY_PREFIX}greenhold")
    take, deliver = spec["steps"]
    assert take["on_take"] == f"{PARCEL_PREFIX}greenhold", "beat 1 picks up the source's parcel"
    assert deliver["on_enter"] == "elderwatch", "beat 2 arrives at the destination town"
    assert deliver["effect"] == "award_xp" and take.get("effect") is None


def test_the_parcel_item_is_placed_at_the_source_town():
    _, parcels = generate_deliveries(_TOWNS)
    assert f"{PARCEL_PREFIX}greenhold" in parcels
    parcel = parcels[f"{PARCEL_PREFIX}greenhold"]
    assert parcel["location"] == "room:greenhold"
    assert "parcel" in parcel["keywords"] and parcel["slot"] == "", "a carried good, not gear"
    assert "Elderwatch" in parcel["name"], "the parcel names where it is bound"


def test_fewer_than_two_towns_route_nothing_and_forging_is_deterministic():
    assert generate_deliveries([_TOWNS[0]]) == ([], {})
    assert generate_deliveries(_TOWNS) == generate_deliveries(_TOWNS)
