"""Contract tests for the AccountCredentialStore port -- proof the credential boundary is clean.

One behavioral contract, run against BOTH adapters: the pure in-memory store (the contract test) and
the SQLAlchemy store over the quarantined tmp database (the integration test). Both must satisfy the
same port, so account persistence can be swapped without touching the crypto -- the assimilation
pattern (docs/persistence_ports.md) applied to auth. The security policy (salted pbkdf2,
constant-time compare, the missing-principal timing decoy, generic refusals) stays in
kernel/world/accounts.py and is pinned by tests/test_accounts.py; this file pins only the storage
boundary and that the domain functions run over an injected store with no database at all.
"""

from __future__ import annotations

import pytest

from kernel.world.accounts import (
    AccountCredentialStore,
    AccountSecret,
    InMemoryAccountCredentialStore,
    account_password_ok,
    reforge_secret,
    register,
    rotate_account_secret,
)
from kernel.world.accounts_sql import SqlAccountCredentialStore

# --- the contract: every AccountCredentialStore must obey these ------------------------


@pytest.fixture(params=["memory", "sql"])
def store(request):
    if request.param == "memory":
        return InMemoryAccountCredentialStore()
    return SqlAccountCredentialStore()


def test_an_unknown_account_finds_nothing(store):
    assert store.find("no-such-account") is None


def test_create_then_find_round_trips(store):
    store.create("matlabs", "aa11", "beefcafe")
    assert store.find("matlabs") == AccountSecret("aa11", "beefcafe")


def test_set_secret_rotates_an_existing_account(store):
    store.create("matlabs", "aa11", "old_digest")
    store.set_secret("matlabs", "bb22", "new_digest")
    assert store.find("matlabs") == AccountSecret("bb22", "new_digest")


def test_set_secret_on_a_missing_account_is_a_silent_noop(store):
    store.set_secret("ghost", "cc33", "whatever")  # no such account
    assert store.find("ghost") is None


def test_both_adapters_satisfy_the_port():
    assert isinstance(InMemoryAccountCredentialStore(), AccountCredentialStore)
    assert isinstance(SqlAccountCredentialStore(), AccountCredentialStore)


# --- the domain functions run over an injected store, no database touched --------------


def test_the_credential_path_runs_entirely_on_an_injected_store():
    """register -> check -> rotate -> reforge over a pure in-memory store: the auth-credential
    domain no longer needs the framework. Crypto still runs (mixed case survives, wrong rejected),
    but nothing hits SQLAlchemy."""
    mem = InMemoryAccountCredentialStore()

    assert register("hero", "matlabs", "StArTeR1", store=mem) == ""  # new account created
    assert account_password_ok("matlabs", "StArTeR1", store=mem) is True
    assert account_password_ok("matlabs", "starter1", store=mem) is False  # case is not mangled
    assert account_password_ok("nobody", "StArTeR1", store=mem) is False  # unknown -> generic False

    # wrong account password on a second registration is refused, right one extends
    assert "not its password" in register("duelist", "matlabs", "wrongpass", store=mem)
    assert register("duelist", "matlabs", "StArTeR1", store=mem) == ""

    rotated = rotate_account_secret("matlabs", "FreshPw42!", store=mem)
    assert rotated == "Password rotated for matlabs."
    assert account_password_ok("matlabs", "FreshPw42!", store=mem) is True
    assert account_password_ok("matlabs", "StArTeR1", store=mem) is False  # old secret is dead

    assert reforge_secret("matlabs", "wrong", "AnotherPw9", store=mem)  # bad old -> refusal string
    assert reforge_secret("matlabs", "FreshPw42!", "AnotherPw9", store=mem) == ""
    assert account_password_ok("matlabs", "AnotherPw9", store=mem) is True


def test_a_too_short_password_is_refused_before_the_store_is_touched():
    mem = InMemoryAccountCredentialStore()
    assert "at least 8" in register("hero", "matlabs", "short", store=mem)
    assert mem.find("matlabs") is None  # nothing was created


# --- the one-time legacy importer, now over the store ----------------------------------


def test_import_legacy_json_reports_nothing_when_no_files_are_present(tmp_path, monkeypatch):
    from kernel.world.accounts import import_legacy_json

    monkeypatch.chdir(tmp_path)  # an empty working dir -- no characters.json / accounts.json
    assert "No legacy JSON found" in import_legacy_json()


def test_import_legacy_json_moves_accounts_and_links_their_characters(tmp_path, monkeypatch):
    """The importer creates account credentials through the store and links each listed character
    onto its account -- proven end to end by a real login afterwards."""
    import json

    import kernel.world.accounts as acc
    from kernel.world.accounts import import_legacy_json, inspect_login
    from kernel.world.characters import load_character

    monkeypatch.chdir(tmp_path)
    (tmp_path / "characters.json").write_text(
        json.dumps({"matrym": {"job": "engineer", "level": 2, "location": "courtyard"}}),
        encoding="utf-8",
    )
    salt = b"\x01" * 16
    entry = {
        "auth": {"salt": salt.hex(), "hash": acc._hash_secret("swordfish", salt)},
        "characters": ["matrym"],
    }
    # a second account with no auth and a member that has no character record exercises the
    # importer's skip branches (create only when auth present; link only when the character exists).
    accounts = {"matlabs": entry, "authless": {"characters": ["ghost_char"]}}
    (tmp_path / "accounts.json").write_text(json.dumps(accounts), encoding="utf-8")

    msg = import_legacy_json()
    assert "Imported 1 character" in msg
    assert load_character("matrym") is not None  # character record landed
    assert inspect_login("matrym", "matlabs", "swordfish")  # account made + character linked
    assert not account_password_ok("authless", "anything")  # authless entry made no account


# --- refusal paths on the store-routed functions ---------------------------------------


def test_rotate_refuses_a_too_short_or_unknown_account():
    mem = InMemoryAccountCredentialStore()
    assert "at least 8" in rotate_account_secret("matlabs", "short", store=mem)  # too short
    assert "No account named" in rotate_account_secret("ghost", "longenough1", store=mem)  # unknown


def test_migrate_refuses_missing_char_missing_password_and_taken_account():
    from kernel.world.accounts import migrate, set_password
    from kernel.world.characters import save_character
    from kernel.world.session import SESSIONS, Session

    SESSIONS.clear()
    mem = InMemoryAccountCredentialStore()
    assert "No saved character" in migrate("nobody", "matlabs", store=mem)  # no character

    hero = Session(player_id="matrym", location="courtyard", named=True)
    SESSIONS["matrym"] = hero
    save_character(hero)
    assert "no password to migrate" in migrate("matrym", "matlabs", store=mem)  # no v1 auth

    set_password("matrym", "swordfish")
    mem.create("matlabs", "aa11", "beefcafe")  # the target account already exists
    assert "already exists" in migrate("matrym", "matlabs", store=mem)
    SESSIONS.clear()
