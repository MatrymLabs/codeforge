"""Contract tests for the AccountCredentialStore port -- proof the credential boundary is clean.

One behavioral contract, run against BOTH adapters: the pure in-memory store (the contract test) and
the SQLAlchemy store over the quarantined tmp database (the integration test). Both must satisfy the
same port, so account persistence can be swapped without touching the crypto -- the assimilation
pattern (docs/persistence_ports.md) applied to auth. The security policy (salted pbkdf2,
constant-time compare, the missing-principal timing decoy, generic refusals) stays in
parts/world/accounts.py and is pinned by tests/test_accounts.py; this file pins only the storage
boundary and that the domain functions run over an injected store with no database at all.
"""

from __future__ import annotations

import pytest

from parts.world.accounts import (
    AccountCredentialStore,
    AccountSecret,
    InMemoryAccountCredentialStore,
    account_password_ok,
    reforge_secret,
    register,
    rotate_account_secret,
)
from parts.world.accounts_sql import SqlAccountCredentialStore

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
