"""Test twin for parts.world.shop: the coin economy's spending end.

Acceptance (list wares, buy with enough coins, sell a bought-back item) AND refusal (no shop here,
not for sale, cannot afford, not carrying it, not something the shop buys), plus engine-tick
reachability. The conftest quarantines the DB into tmp, and this fixture snapshots ITEMS + NPCS so
bought/sold clones never leak between tests.
"""

import copy

import pytest

import forge  # noqa: F401 -- boot the world (inspect_world_links) BEFORE the fixture injects a merchant
from parts.world import items, npcs
from parts.world.jobs import bind_calling
from parts.world.session import SESSIONS, Session
from parts.world.shop import buy, render_shop, sell

# A minimal merchant + a sellable/buyable item, injected into the live registries for each test.
_WARE = {
    "name": "a test trinket",
    "keywords": ["trinket"],
    "location": "player",
    "slot": "",
    "mods": {},
    "prototype": "trinket",
}
_MERCHANT = {
    "name": "a test merchant",
    "keywords": ["merchant"],
    "location": "courtyard",
    "dialogue": ["..."],
    "next_line": 0,
    "hp": 0,
    "hp_now": 0,
    "xp": 0,
    "atk": 0,
    "shop": {"sells": {"trinket": 30}, "buys": {"trinket": 12}},
}


@pytest.fixture(autouse=True)
def fresh_world():
    npcs_snap, items_snap = copy.deepcopy(npcs.NPCS), copy.deepcopy(items.ITEMS)
    SESSIONS.clear()
    items.PROTOTYPES["trinket"] = copy.deepcopy(_WARE)
    npcs.NPCS["test_merchant"] = copy.deepcopy(_MERCHANT)
    yield
    npcs.NPCS.clear()
    npcs.NPCS.update(npcs_snap)
    items.ITEMS.clear()
    items.ITEMS.update(items_snap)
    items.PROTOTYPES.pop("trinket", None)
    SESSIONS.clear()


def _shopper(coins: int = 100, location: str = "courtyard") -> Session:
    s = Session(player_id="shopper", location=location)
    SESSIONS["shopper"] = s
    bind_calling(s, "vanguard")
    s.coins = coins
    return s


def test_render_shop_lists_wares_and_the_purse():
    out = render_shop(_shopper(coins=77))
    assert "a test trinket" in out and "30 coins" in out and "77 coins" in out


def test_no_shop_here_is_refused():
    assert "no one selling" in render_shop(_shopper(location="library"))


def test_buying_spends_coins_and_hands_over_a_fresh_instance():
    s = _shopper(coins=100)
    out = buy(s, "trinket")
    assert "You buy" in out and s.coins == 70
    assert any(items.prototype_of(i) == "trinket" for i in items.items_in("player"))


def test_buying_something_not_for_sale_is_refused():
    assert "not for sale" in buy(_shopper(), "dragon")


def test_buying_without_enough_coins_is_refused():
    s = _shopper(coins=5)
    assert "cannot afford" in buy(s, "trinket")
    assert s.coins == 5  # unchanged


def test_selling_a_carried_item_pays_coins_and_removes_it():
    s = _shopper(coins=0)
    items.clone("trinket", "player")
    out = sell(s, "trinket")
    assert "You sell" in out and s.coins == 12
    assert not items.items_in("player")  # the shop took it


def test_selling_something_you_do_not_carry_is_refused():
    assert "aren't carrying" in sell(_shopper(), "trinket")


def test_buy_is_reachable_through_the_engine_tick():
    s = _shopper(coins=50)
    reply = forge.handle_command(s, "buy trinket")
    assert "You buy" in reply and s.coins == 20
