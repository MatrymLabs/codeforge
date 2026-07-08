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
    assert "at least 8" in set_password("matrym", "abc")
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


# --------------------------------------------------------- character@account


def _tick(session, text):
    return handle_command(session, text)


def _fresh(pid="p1"):
    s = Session(player_id=pid)
    SESSIONS[pid] = s
    return s


def test_register_creates_account_character_and_seat():
    s = _fresh()
    out = _tick(s, "register matrym@matlabs swordfish")
    assert "Welcome, Matrym@matlabs" in out
    assert s.player_id == "matrym"
    assert s.account == "matlabs"
    assert load_character("matrym") is not None


def test_register_second_character_needs_the_account_password():
    s = _fresh()
    _tick(s, "register matrym@matlabs swordfish")
    _tick(s, "quit")
    SESSIONS.clear()
    alt = _fresh()
    assert "not its password" in _tick(alt, "register duelist@matlabs wrongpass")
    out = _tick(alt, "register duelist@matlabs swordfish")
    assert "Welcome, Duelist@matlabs" in out


def test_register_cannot_hijack_an_existing_character():
    s = _fresh()
    _tick(s, "register matrym@matlabs swordfish")
    SESSIONS.clear()
    thief = _fresh()
    assert "already exists" in _tick(thief, "register matrym@evilcorp hunter2x")


def test_login_restores_the_character_with_one_generic_refusal():
    s = _fresh()
    _tick(s, "register matrym@matlabs swordfish")
    s.level = 2
    _tick(s, "quit")
    SESSIONS.clear()
    back = _fresh()
    assert "do not align" in _tick(back, "login matrym@matlabs wrong")
    assert "do not align" in _tick(back, "login matrym@nosuch swordfish")
    assert "do not align" in _tick(back, "login stranger@matlabs swordfish")
    out = _tick(back, "login matrym@matlabs swordfish")
    assert "Welcome back, Matrym@matlabs" in out
    assert back.level == 2


def test_handles_must_be_well_formed():
    s = _fresh()
    assert "Usage:" in _tick(s, "login matrym swordfish")
    assert "Usage:" in _tick(s, "register matrym@matlabs")


def test_migrate_moves_a_character_password_onto_a_new_account():
    from parts.accounts import inspect_login, migrate

    hero = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = hero
    save_character(hero)
    set_password("matrym", "swordfish")
    msg = migrate("matrym", "matlabs")
    assert "matrym@matlabs is ready" in msg
    assert inspect_login("matrym", "matlabs", "swordfish")
    assert not has_password(load_character("matrym"))  # char auth retired


def test_mixed_case_passwords_survive_the_tick():
    """Regression: the tick must never lowercase a secret. This is the
    bug that ate a week of rotations -- CLI-set true-case passwords
    failed at the door because raw.lower() mangled them."""

    s = _fresh()
    _tick(s, "register matrym@matlabs StArTeR1")
    _tick(s, "quit")
    SESSIONS.clear()
    back = _fresh()
    assert "Welcome back" in _tick(back, "login matrym@matlabs StArTeR1")
    SESSIONS.clear()
    impostor = _fresh("p2")
    assert "do not align" in _tick(impostor, "login matrym@matlabs starter1")


def test_cli_rotation_then_tick_login_roundtrip():
    """The exact saga, pinned forever: passwd via CLI, login via door."""
    from parts.accounts import rotate_account_secret

    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    _tick(s, "quit")
    SESSIONS.clear()
    rotate_account_secret("matlabs", "MiXedCase42!")
    back = _fresh()
    out = _tick(back, "login matrym@matlabs MiXedCase42!")
    assert "Welcome back, Matrym@matlabs" in out


# ----------------------------------------------- passwd (in-game self-service)


def test_passwd_changes_the_account_password_end_to_end():
    """The whole point: never touch the CLI. Rotate in-world, then the
    new secret opens the door and the old one is dead."""
    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "Password changed" in _tick(s, "passwd starter1 fresh_pw2 fresh_pw2")
    _tick(s, "quit")
    SESSIONS.clear()
    back = _fresh()
    assert "do not align" in _tick(back, "login matrym@matlabs starter1")  # old is dead
    assert "Welcome back, Matrym@matlabs" in _tick(back, "login matrym@matlabs fresh_pw2")


def test_passwd_refuses_the_wrong_old_password():
    from parts.accounts import account_password_ok

    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "not your current password" in _tick(s, "passwd wrongold newpass9 newpass9")
    assert account_password_ok("matlabs", "starter1")  # nothing rotated


def test_passwd_refuses_mismatched_new_passwords():
    from parts.accounts import account_password_ok

    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "do not match" in _tick(s, "passwd starter1 newpass9 different9")
    assert account_password_ok("matlabs", "starter1")  # nothing rotated


def test_passwd_preserves_mixed_case_roundtrip():
    """The saga's rule applied to self-service: a mixed-case NEW password
    must log in with its true case and reject the lowered one."""
    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "Password changed" in _tick(s, "passwd starter1 MiXeD_Pw9 MiXeD_Pw9")
    _tick(s, "quit")
    SESSIONS.clear()
    back = _fresh()
    assert "do not align" in _tick(back, "login matrym@matlabs mixed_pw9")  # lowered fails
    assert "Welcome back" in _tick(back, "login matrym@matlabs MiXeD_Pw9")


def test_passwd_requires_an_account():
    guest = _fresh()  # a seat with no account
    assert "Only account logins" in _tick(guest, "passwd anything newpass9 newpass9")


def test_passwd_refuses_a_too_short_new_password():
    from parts.accounts import account_password_ok

    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "at least 8" in _tick(s, "passwd starter1 no no")
    assert account_password_ok("matlabs", "starter1")  # nothing rotated


def test_passwd_shows_usage_on_wrong_shape():
    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "Usage: passwd" in _tick(s, "passwd starter1 lonely")  # missing confirm


def test_password_floor_is_eight_characters():
    from parts.accounts import MIN_PASSWORD_LEN

    assert MIN_PASSWORD_LEN == 8
    s = _fresh()
    assert "at least 8" in _tick(s, "register short@acct sevench")  # 7 chars refused
    assert "Welcome, Short@acct" in _tick(s, "register short@acct eightchr")  # 8 chars ok


def test_reforge_secret_directly_verifies_then_rotates():
    from parts.accounts import account_password_ok, reforge_secret

    s = _fresh()
    _tick(s, "register matrym@matlabs starter1")
    assert "not your current password" in reforge_secret("matlabs", "wrong", "fresh_pw2")
    assert account_password_ok("matlabs", "starter1")  # bad old changed nothing
    assert reforge_secret("matlabs", "starter1", "fresh_pw2") == ""
    assert account_password_ok("matlabs", "fresh_pw2")
    assert not account_password_ok("matlabs", "starter1")
