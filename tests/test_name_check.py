"""Test twin for parts/name_check.py -- the game adapter: validate a proposed name."""

from parts.name_check import name_check
from parts.world.session import SESSIONS, Session


def _player() -> Session:
    s = Session(player_id="matrym", location="courtyard")
    SESSIONS["matrym"] = s
    return s


def test_a_good_name_is_accepted():
    assert "is a valid character name" in name_check(_player(), "ada_lovelace")


def test_an_empty_name_is_refused():
    out = name_check(_player(), "   ")
    assert "won't work" in out
    assert "required" in out


def test_a_malformed_name_explains_why():
    out = name_check(_player(), "1bad name")  # starts with a digit, has a space
    assert "won't work" in out
    assert "lowercase letters" in out


def test_a_reserved_name_is_refused():
    assert "reserved" in name_check(_player(), "admin")


def test_namecheck_flows_through_the_engine_tick():
    from forge import handle_command

    assert "valid character name" in handle_command(_player(), "namecheck scholar_x")
