"""Test twin for kernel/world/trade.py -- the atomic player-to-player swap.

Acceptance: propose + accept opens a trade; staking items and coin then confirming BOTH sides moves
everything at once (items change carrier, coin transfers); the roster renders both sides. Refusal /
safety (the point of a trade): a self-trade, a distant or absent partner, an accept with no offer,
item you do not carry, and coin beyond your purse are all refused. Atomicity: if an offered item is
gone at execute, the WHOLE trade aborts and nothing changes hands; a logout cancels cleanly with no
goods moved, since nothing moves until the atomic seal.
"""

from __future__ import annotations

from kernel.world import events, items, trade
from kernel.world.items import carrier
from kernel.world.session import SESSIONS, Session


def _hero(name: str, room: str = "market", coins: int = 0) -> Session:
    s = SESSIONS[name] = Session(player_id=name, location=room)
    s.coins = coins
    return s


def _give(name: str, iid: str, item_name: str) -> None:
    """Put an item straight into a hero's hands."""
    items.ITEMS[iid] = {
        "name": item_name,
        "keywords": [item_name.split()[-1]],  # noqa: PLC0207
        "location": carrier(name),
        "slot": "",
        "mods": {},
    }


def _open_trade(a: str, b: str) -> None:
    trade.propose(a, b)
    trade.accept(b)


def _teardown() -> None:
    trade._reset()
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)
    for iid in ("ruby", "sword"):
        items.ITEMS.pop(iid, None)


# --- acceptance --------------------------------------------------------------------------------
def test_a_confirmed_trade_swaps_goods_and_coin_atomically():
    try:
        _hero("alia", coins=100)
        _hero("bram", coins=0)
        _give("alia", "ruby", "a ruby")
        _open_trade("alia", "bram")
        trade.add_item("alia", "ruby")
        trade.offer_coins("alia", "30")
        trade.confirm("alia")
        result = trade.confirm("bram")  # both confirmed -> seal
        assert "sealed" in result
        assert items.ITEMS["ruby"]["location"] == carrier("bram")  # the ruby moved
        assert SESSIONS["alia"].coins == 70 and SESSIONS["bram"].coins == 30  # coin transferred
        assert trade._TRADES == {}  # the trade closed
    finally:
        _teardown()


def test_a_replayed_confirm_after_a_sealed_trade_never_re_swaps():
    """Replay / duplicate-request safety (Stage 5): once a trade has sealed it is popped
    from the registry, so a second `confirm` from either party finds no open trade and
    moves nothing -- a double-sent confirm cannot duplicate the goods or coin already
    swapped."""
    try:
        _hero("alia", coins=100)
        _hero("bram", coins=0)
        _give("alia", "ruby", "a ruby")
        _open_trade("alia", "bram")
        trade.add_item("alia", "ruby")
        trade.offer_coins("alia", "30")
        trade.confirm("alia")
        assert "sealed" in trade.confirm("bram")  # the swap fires exactly once
        assert items.ITEMS["ruby"]["location"] == carrier("bram")
        assert (SESSIONS["alia"].coins, SESSIONS["bram"].coins) == (70, 30)
        # replay the winning move from BOTH sides
        assert "not in a trade" in trade.confirm("bram").lower()
        assert "not in a trade" in trade.confirm("alia").lower()
        # the ruby and the coin moved once and only once
        assert items.ITEMS["ruby"]["location"] == carrier("bram")
        assert (SESSIONS["alia"].coins, SESSIONS["bram"].coins) == (70, 30)
    finally:
        _teardown()


def test_render_shows_both_sides_and_confirmation():
    try:
        _hero("alia")
        _hero("bram")
        _give("alia", "ruby", "a ruby")
        _open_trade("alia", "bram")
        trade.add_item("alia", "ruby")
        trade.confirm("alia")
        out = trade.render("bram")
        assert "a ruby" in out and "[confirmed]" in out and "You: nothing" in out
    finally:
        _teardown()


def test_changing_an_offer_after_confirming_voids_both_confirmations():
    try:
        _hero("alia")
        _hero("bram")
        _give("alia", "ruby", "a ruby")
        _give("alia", "sword", "a sword")
        _open_trade("alia", "bram")
        trade.add_item("alia", "ruby")
        trade.confirm("alia")
        trade.add_item("alia", "sword")  # a change after confirming
        assert not trade._TRADES["alia"].offers["alia"].confirmed  # un-confirmed
    finally:
        _teardown()


# --- refusal / safety --------------------------------------------------------------------------
def test_a_self_trade_and_a_distant_partner_are_refused():
    try:
        _hero("alia", room="market")
        _hero("bram", room="the-deep")  # elsewhere
        assert "yourself" in trade.propose("alia", "alia").lower()
        assert "not here" in trade.propose("alia", "bram").lower()
        assert trade._TRADES == {}
    finally:
        _teardown()


def test_accept_with_no_offer_is_refused():
    try:
        _hero("alia")
        assert "no one" in trade.accept("alia").lower()
    finally:
        _teardown()


def test_you_cannot_stake_an_item_you_do_not_carry_or_coin_you_lack():
    try:
        _hero("alia", coins=10)
        _hero("bram")
        _open_trade("alia", "bram")
        assert "aren't carrying" in trade.add_item("alia", "dragon").lower()
        assert "do not have that many" in trade.offer_coins("alia", "999").lower()
    finally:
        _teardown()


def test_the_trade_aborts_atomically_if_an_offered_item_vanishes():
    try:
        _hero("alia", coins=50)
        _hero("bram", coins=50)
        _give("alia", "ruby", "a ruby")
        _open_trade("alia", "bram")
        trade.add_item("alia", "ruby")
        trade.offer_coins("bram", "20")
        trade.confirm("alia")
        # alia's ruby leaves her hands (dropped) AFTER she staked it, before bram seals
        items.ITEMS["ruby"]["location"] = "room:market"
        result = trade.confirm("bram")  # execute validates -> fails
        assert "fails" in result.lower()
        # NOTHING moved: bram keeps his coin, alia's purse untouched, the ruby still on the floor
        assert SESSIONS["bram"].coins == 50 and SESSIONS["alia"].coins == 50
        assert items.ITEMS["ruby"]["location"] == "room:market"
        assert trade._TRADES == {}  # the failed trade closed
    finally:
        _teardown()


def test_a_logout_cancels_an_open_trade_with_nothing_moved():
    try:
        _hero("alia", coins=40)
        _hero("bram", coins=40)
        _give("alia", "ruby", "a ruby")
        _open_trade("alia", "bram")
        trade.add_item("alia", "ruby")
        trade.offer_coins("alia", "10")
        trade.on_disconnect("alia")  # alia logs out mid-trade
        assert trade._TRADES == {}  # trade cancelled
        assert SESSIONS["bram"].coins == 40  # bram untouched
        assert items.ITEMS["ruby"]["location"] == carrier("alia")  # ruby never left alia's bag
    finally:
        _teardown()


# --- the verb is reachable through the engine tick ---------------------------------------------
def test_the_trade_verb_is_reachable():
    import forge  # noqa: PLC0415

    try:
        _hero("alia")
        _hero("bram")
        assert "offer to trade" in forge.handle_command(SESSIONS["alia"], "trade bram").lower()
        assert "open a trade" in forge.handle_command(SESSIONS["bram"], "trade accept").lower()
    finally:
        _teardown()
