"""Test twin for parts.world.orders: the Orders faction allegiance primitive.

Acceptance (a named hero swears and it persists) AND refusal (unnamed, unknown Order) cases, plus
engine-tick reachability (a feature isn't wired until handle_command proves it) and a persistence
round-trip. The conftest quarantines the DB into tmp, so save/load never touch real state.
"""

from parts.world.characters import load_character, save_character
from parts.world.orders import ORDERS, order_name, swear_order
from parts.world.session import Session


def _hero(named: bool = True, location: str = "orders_row") -> Session:
    s = Session(player_id="swornhero", location=location)
    s.named = named
    return s


def test_the_four_bible_orders_are_on_the_roster():
    assert set(ORDERS) == {"making", "gathering", "warcraft", "knowing"}
    for order in ORDERS.values():
        assert order["name"] and order["creed"]  # each has a display name and a creed


def test_order_name_resolves_a_label_and_is_empty_for_unknown():
    assert order_name("warcraft") == "the Warcraft Order"
    assert order_name("dragons") == ""  # unknown -> empty, never a crash


def test_bare_join_lists_the_roster():
    out = swear_order(_hero(), "")
    assert "The Orders of the Row" in out
    assert "warcraft" in out and "knowing" in out


def test_an_unnamed_session_cannot_swear():
    assert "named Forger" in swear_order(_hero(named=False), "warcraft")  # refusal, loud


def test_an_unknown_order_is_refused_with_the_roster():
    out = swear_order(_hero(), "dragons")
    assert "no Order called" in out and "The Orders of the Row" in out


def test_a_named_hero_swears_and_the_allegiance_sticks():
    s = _hero()
    out = swear_order(s, "warcraft")
    assert s.order == "warcraft"
    assert "the Warcraft Order" in out and ORDERS["warcraft"]["creed"] in out


def test_swearing_the_same_order_twice_is_a_gentle_no_op():
    s = _hero()
    swear_order(s, "making")
    assert "already sworn" in swear_order(s, "making")
    assert s.order == "making"  # unchanged


def test_join_is_reachable_through_the_engine_tick():
    from forge import handle_command

    s = _hero()
    reply = handle_command(s, "join knowing")
    assert "the Knowing Order" in reply and s.order == "knowing"


def test_the_sworn_order_persists_across_a_save_and_load():
    s = _hero()
    swear_order(s, "gathering")
    save_character(s)
    casefile = load_character("swornhero")
    assert casefile is not None and casefile["order"] == "gathering"
