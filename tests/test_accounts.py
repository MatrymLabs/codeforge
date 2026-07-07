"""Test twin for parts/accounts.py -- names with proof."""

import pytest

from forge import handle_command
from parts.accounts import has_password, set_password, verify_password
from parts.characters import load_character, save_character
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def _saved_hero(name: str = "matrym") -> Session:
    s = Session(player_id=name, location="courtyard", named=True)
    SESSIONS[name] = s
    save_character(s)
    return s


def test_password_hash_is_salted_and_never_plaintext():
    _saved_hero("matrym")
    _saved_hero("rando")
    set_password("matrym", "swordfish")
    set_password("rando", "swordfish")
    a, b = load_character("matrym"), load_character("rando")
    assert "swordfish" not in str(a["auth"])
    assert a["auth"]["hash"] != b["auth"]["hash"]  # same password, different salt


def test_verify_roundtrip_and_rejection():
    _saved_hero()
    set_password("matrym", "swordfish")
    assert verify_password("matrym", "swordfish")
    assert not verify_password("matrym", "SWORDFISH")
    assert not verify_password("matrym", "")
    assert not verify_password("stranger", "swordfish")


def test_short_passwords_are_refused():
    _saved_hero()
    assert "at least 4" in set_password("matrym", "abc")
    assert not has_password(load_character("matrym"))


def test_protected_name_refuses_impostors_at_the_tick():
    hero = _saved_hero()
    set_password("matrym", "swordfish")
    handle_command(hero, "quit")
    SESSIONS.clear()
    impostor = Session(player_id="player1")
    SESSIONS["player1"] = impostor
    out = handle_command(impostor, "name matrym")
    assert "That name is protected" in out
    assert impostor.player_id == "player1"  # the re-key never happened
    assert "player1" in SESSIONS


def test_protected_name_opens_with_the_password():
    hero = _saved_hero()
    set_password("matrym", "swordfish")
    handle_command(hero, "quit")
    SESSIONS.clear()
    returning = Session(player_id="player1")
    SESSIONS["player1"] = returning
    out = handle_command(returning, "name matrym swordfish")
    assert "Welcome back, Matrym." in out
    assert returning.player_id == "matrym"


def test_passwordless_legacy_names_restore_with_a_nag():
    hero = _saved_hero()
    handle_command(hero, "quit")
    SESSIONS.clear()
    returning = Session(player_id="player1")
    SESSIONS["player1"] = returning
    out = handle_command(returning, "name matrym")
    assert "Welcome back, Matrym." in out
    assert "no password" in out


def test_password_command_requires_a_claimed_name():
    anon = Session(player_id="player1")
    SESSIONS["player1"] = anon
    assert "Claim a name first" in handle_command(anon, "password swordfish")
