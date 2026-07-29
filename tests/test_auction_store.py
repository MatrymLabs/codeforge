"""Test twin for parts/world/auction_store.py -- the escrowed-listing adapter.

Acceptance: a created listing appears in active() and get() with its item snapshot, price, and
seller; buy() removes and returns it. Refusal: buy() succeeds exactly once (a second returns None,
so two buyers can never both win); expired() reads only lapsed; remove() is idempotent. Real table,
quarantined to tmp by conftest.
"""

from __future__ import annotations

from parts.world import auction_store


def _snap(name: str = "a wrench", rarity: str = "common", mods: dict | None = None) -> dict:
    return {"prototype": "forge_wrench", "name": name, "mods": mods or {}, "rarity": rarity}


def test_a_created_listing_is_active_and_readable():
    lid = auction_store.create("ada", _snap("a Cruel wrench [rare]", "rare", {"ATK": 5}), 75, 900)
    listing = auction_store.get(lid)
    assert listing is not None
    assert listing.seller == "ada" and listing.price == 75 and listing.expiry_beat == 900
    assert listing.item["name"] == "a Cruel wrench [rare]"
    assert listing.item["mods"] == {"ATK": 5} and listing.item["rarity"] == "rare"
    assert [x.id for x in auction_store.active()] == [lid]


def test_buy_removes_and_returns_exactly_once():
    lid = auction_store.create("ada", _snap(), 20, 900)
    first = auction_store.buy(lid)
    assert first is not None and first.price == 20
    assert auction_store.buy(lid) is None  # gone: no second sale
    assert auction_store.active() == []


def test_get_and_buy_a_missing_listing_return_none():
    assert auction_store.get(4242) is None
    assert auction_store.buy(4242) is None


def test_expired_reads_only_lapsed_listings():
    auction_store.create("ada", _snap("old"), 10, expiry_beat=5)
    auction_store.create("bram", _snap("fresh"), 10, expiry_beat=1000)
    lapsed = auction_store.expired(now_beat=100)  # only the one due at 5
    assert [x.item["name"] for x in lapsed] == ["old"]


def test_remove_is_idempotent():
    lid = auction_store.create("ada", _snap(), 10, 900)
    auction_store.remove(lid)
    assert auction_store.get(lid) is None
    auction_store.remove(lid)  # a second remove is a harmless no-op, not a crash
