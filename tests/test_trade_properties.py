"""Property tests: the economy's money-integrity invariants under the atomic player trade.

The player-to-player trade (parts/world/trade.py) MOVES currency and items, so it is an economy
security boundary: a bug here is coin or item duplication or destruction. Hypothesis pins the
invariants across hundreds of generated offers, not a handful of examples (Phase 9/12 of the
developer-security campaign, economy + duplication testing):

  - currency is CONSERVED across a trade -- no coin is ever created or destroyed;
  - a balance never goes negative;
  - an over-balance or negative offer is refused (no overspend);
  - a sealed item trade leaves the item with exactly ONE owner (no dupe, no loss);
  - an aborted trade leaves NO partial state (atomicity).

Any failure here would become a deterministic regression test.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from parts.world import events, items, trade
from parts.world.items import carrier, items_in
from parts.world.session import SESSIONS, Session

_A, _B = "alia", "bram"


def _reset() -> None:
    trade._reset()
    for name in list(SESSIONS):
        events.unbind_echo(name)
        SESSIONS.pop(name, None)
    for iid in ("ruby", "sword"):
        items.ITEMS.pop(iid, None)


def _hero(name: str, coins: int) -> None:
    SESSIONS[name] = Session(player_id=name, location="market")
    SESSIONS[name].coins = coins


def _seal(a_coins: int, b_coins: int, a_offer: int, b_offer: int) -> str:
    """Run a full two-sided coin trade and return the seal/abort result string."""
    _hero(_A, a_coins)
    _hero(_B, b_coins)
    trade.propose(_A, _B)
    trade.accept(_B)
    trade.offer_coins(_A, str(a_offer))
    trade.offer_coins(_B, str(b_offer))
    trade.confirm(_A)
    return trade.confirm(_B)


@pytest.mark.property
@given(
    a_coins=st.integers(0, 1_000_000),
    b_coins=st.integers(0, 1_000_000),
    a_offer=st.integers(
        -10, 1_000_000
    ),  # includes over-balance and negative offers (must be refused)
    b_offer=st.integers(-10, 1_000_000),
)
@settings(max_examples=300, deadline=None)
def test_a_trade_conserves_currency_and_never_goes_negative(a_coins, b_coins, a_offer, b_offer):
    _reset()
    try:
        total_before = a_coins + b_coins
        _seal(a_coins, b_coins, a_offer, b_offer)
        after_a, after_b = SESSIONS[_A].coins, SESSIONS[_B].coins
        # Universal invariant: whether the trade sealed or aborted, the two purses sum to the same
        # total and neither is negative. No offer (valid, over-balance, or negative) can mint coin.
        assert after_a + after_b == total_before
        assert after_a >= 0 and after_b >= 0
    finally:
        _reset()


@st.composite
def _valid_offers(draw):
    a_coins = draw(st.integers(0, 1_000_000))
    b_coins = draw(st.integers(0, 1_000_000))
    a_offer = draw(st.integers(0, a_coins))  # within balance, so the offer is accepted
    b_offer = draw(st.integers(0, b_coins))
    return a_coins, b_coins, a_offer, b_offer


@pytest.mark.property
@given(_valid_offers())
@settings(max_examples=300, deadline=None)
def test_a_sealed_trade_moves_exactly_the_offered_amounts(offers):
    a_coins, b_coins, a_offer, b_offer = offers
    _reset()
    try:
        result = _seal(a_coins, b_coins, a_offer, b_offer)
        assert "sealed" in result  # both offers are within balance, so it seals
        # each side ends with: its purse, minus what it gave, plus what it received
        assert SESSIONS[_A].coins == a_coins - a_offer + b_offer
        assert SESSIONS[_B].coins == b_coins - b_offer + a_offer
    finally:
        _reset()


@pytest.mark.property
@given(a_coins=st.integers(0, 10_000), b_coins=st.integers(0, 10_000))
@settings(max_examples=100, deadline=None)
def test_a_sealed_item_trade_leaves_exactly_one_owner(a_coins, b_coins):
    _reset()
    try:
        _hero(_A, a_coins)
        _hero(_B, b_coins)
        items.ITEMS["ruby"] = {
            "name": "a ruby",
            "keywords": ["ruby"],
            "location": carrier(_A),
            "slot": "",
            "mods": {},
        }
        before_count = len(items.ITEMS)
        trade.propose(_A, _B)
        trade.accept(_B)
        trade.add_item(_A, "ruby")
        trade.confirm(_A)
        assert "sealed" in trade.confirm(_B)
        # the item moved to exactly one owner: with the receiver, not the giver, never duplicated
        assert "ruby" in items_in(carrier(_B))
        assert "ruby" not in items_in(carrier(_A))
        assert len(items.ITEMS) == before_count  # no clone, no loss
    finally:
        _reset()


@pytest.mark.property
@given(a_coins=st.integers(1, 10_000), a_offer_frac=st.integers(1, 100))
@settings(max_examples=100, deadline=None)
def test_an_aborted_trade_leaves_no_partial_state(a_coins, a_offer_frac):
    # Stake coin, then make the trade un-sealable (the offered item vanishes) and confirm: the whole
    # trade must abort with NEITHER coin nor item moved -- validate-all-then-apply atomicity.
    _reset()
    try:
        a_offer = max(1, a_coins * a_offer_frac // 100)
        _hero(_A, a_coins)
        _hero(_B, 0)
        items.ITEMS["ruby"] = {
            "name": "a ruby",
            "keywords": ["ruby"],
            "location": carrier(_A),
            "slot": "",
            "mods": {},
        }
        trade.propose(_A, _B)
        trade.accept(_B)
        trade.add_item(_A, "ruby")
        trade.offer_coins(_A, str(a_offer))
        trade.confirm(_A)
        items.ITEMS["ruby"]["location"] = "room:void"  # the staked item leaves the giver's hand
        result = trade.confirm(_B)
        assert "fails" in result or "abort" in result.lower()
        # nothing moved: the giver kept every coin, the receiver gained none
        assert SESSIONS[_A].coins == a_coins and SESSIONS[_B].coins == 0
    finally:
        _reset()
