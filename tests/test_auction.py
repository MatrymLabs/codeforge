"""Test twin for parts/world/auction.py + auction_store.py -- the marketplace.

Acceptance: listing escrows a carried item out of the world; browse shows it; buying pays the seller
(online OR offline) and re-clones the item into the buyer's bag while the listing vanishes; an
unsold listing is mailed back to its seller on the expiry sweep. Refusal: a bad price, a worn or
uncarried item, buying your own listing, buying with too little coin, and buying a gone listing are
all refused; and a listing can be bought exactly once (no double-sale, no dupe). Real store, tmp.
"""

from __future__ import annotations

import copy

import pytest

from parts.world import auction, auction_store, items, mail_store
from parts.world.character_store import CharacterRecord
from parts.world.characters import _default_store, load_character
from parts.world.items import ITEMS, carrier, items_in, prototype_of
from parts.world.jobs import bind_calling
from parts.world.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def _fresh_items():
    snap = copy.deepcopy(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(snap)


def _hero(name: str, coins: int = 0) -> Session:
    s = SESSIONS[name] = Session(player_id=name, location="courtyard", named=True)
    s.coins = coins
    bind_calling(s, "vanguard")
    return s


def _teardown() -> None:
    for name in list(SESSIONS):
        SESSIONS.pop(name, None)


def _snap(name: str = "a wrench") -> dict:
    return {"prototype": "forge_wrench", "name": name, "mods": {}, "rarity": "common"}


# --- acceptance -------------------------------------------------------------------------------
def test_listing_escrows_the_item_and_browse_shows_it():
    try:
        ada = _hero("ada")
        iid = items.clone("forge_wrench", carrier("ada"))
        out = auction.list_item(ada, "wrench 50")
        assert "list" in out.lower() and "50" in out
        assert iid not in ITEMS  # escrowed: it left the world
        assert len(auction_store.active()) == 1
        assert "50 coins" in auction.browse(ada)
    finally:
        _teardown()


def test_buying_pays_an_online_seller_and_delivers_the_item():
    try:
        ada = _hero("ada")  # seller
        bram = _hero("bram", coins=100)  # buyer
        items.clone("forge_wrench", carrier("ada"))
        auction.list_item(ada, "wrench 60")
        listing_id = auction_store.active()[0].id
        out = auction.buy(bram, str(listing_id))
        assert "buy" in out.lower()
        assert bram.coins == 40  # buyer paid 60
        assert ada.coins == 60  # seller received 60
        assert any(prototype_of(i) == "forge_wrench" for i in items_in(carrier("bram")))
        assert auction_store.active() == []  # the listing is gone
    finally:
        _teardown()


def test_buying_credits_an_offline_seller_on_their_stored_row():
    try:
        # a listing from a seller who is NOT logged in (created straight into escrow)
        _default_store().upsert_full(CharacterRecord(name="offbob", coins=5))
        auction_store.create("offbob", _snap(), 30, expiry_beat=99999)
        bram = _hero("bram", coins=100)
        listing_id = auction_store.active()[0].id
        auction.buy(bram, str(listing_id))
        assert bram.coins == 70
        assert load_character("offbob")["coins"] == 35  # 5 + 30, credited on the row
    finally:
        _teardown()


def test_a_listing_can_be_bought_exactly_once():
    try:
        _default_store().upsert_full(CharacterRecord(name="offbob", coins=0))
        auction_store.create("offbob", _snap(), 10, expiry_beat=99999)
        listing_id = auction_store.active()[0].id
        assert auction_store.buy(listing_id) is not None  # first sale wins
        assert auction_store.buy(listing_id) is None  # second finds nothing (no double-sale)
    finally:
        _teardown()


def test_the_expiry_sweep_mails_an_unsold_item_back_to_its_seller():
    try:
        _default_store().upsert_full(CharacterRecord(name="offbob", coins=0))
        auction_store.create("offbob", _snap("a Cruel wrench [rare]"), 40, expiry_beat=0)  # lapsed
        returned = auction.sweep_expired()  # climate.now() >= 0, so it is expired
        assert returned == 1
        assert auction_store.active() == []  # removed from the market
        letter = mail_store.inbox("offbob")[0]
        assert letter.attachment is not None  # the item rode a letter home
        assert letter.attachment["name"] == "a Cruel wrench [rare]"
    finally:
        _teardown()


# --- refusal / safety --------------------------------------------------------------------------
def test_listing_refuses_a_bad_price_or_a_worn_or_uncarried_item():
    try:
        ada = _hero("ada")
        assert "for how much" in auction.list_item(ada, "wrench").lower()  # no price
        assert "positive" in auction.list_item(ada, "wrench 0").lower()  # non-positive
        assert "aren't carrying" in auction.list_item(ada, "dragon 10").lower()
        iid = items.clone("forge_wrench", carrier("ada"))
        ada.equipped["weapon"] = iid  # worn
        assert "worn" in auction.list_item(ada, "wrench 10").lower()
    finally:
        _teardown()


def test_buying_your_own_or_unaffordable_or_missing_listing_is_refused():
    try:
        ada = _hero("ada", coins=5)
        items.clone("forge_wrench", carrier("ada"))
        auction.list_item(ada, "wrench 50")
        listing_id = auction_store.active()[0].id
        assert "your own" in auction.buy(ada, str(listing_id)).lower()  # seller can't buy own
        bram = _hero("bram", coins=10)
        assert "cannot afford" in auction.buy(bram, str(listing_id)).lower()  # 10 < 50
        assert "no such listing" in auction.buy(bram, "9999").lower()
    finally:
        _teardown()


# --- the verb is reachable through the engine tick --------------------------------------------
def test_the_auction_verb_is_reachable():
    import forge

    try:
        ada = _hero("ada")
        items.clone("forge_wrench", carrier("ada"))
        assert "list" in forge.handle_command(ada, "auction list wrench 25").lower()
        assert "auction house" in forge.handle_command(ada, "auction").lower()
    finally:
        _teardown()
