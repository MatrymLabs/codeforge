"""Contract tests for the MembershipStore port -- proof the last CharacterRow seam is clean.

One behavioral contract, run against BOTH adapters: the pure in-memory store (the contract test) and
the SQLAlchemy store over the quarantined tmp database (the integration test). Both must satisfy the
same port, so account-to-character membership can be swapped without touching the domain -- the last
boundary that makes kernel/world/accounts.py framework-free (docs/persistence_ports.md). The
end-to-end auth behaviour stays pinned by tests/test_accounts.py; this pins the storage boundary
and that adopt / account_has_owner / inspect_login run over injected stores with no database.
"""

from __future__ import annotations

import pytest

from kernel.world.accounts import InMemoryAccountCredentialStore
from kernel.world.membership import InMemoryMembershipStore, MembershipStore
from kernel.world.membership_sql import SqlMembershipStore


def _sql_world() -> SqlMembershipStore:
    """A real character world in the tmp DB: rowan (no account, player), regent (kingdom, owner)."""
    from kernel.world.characters import save_character  # noqa: PLC0415
    from kernel.world.session import SESSIONS, Session  # noqa: PLC0415

    SESSIONS.clear()
    rowan = Session(player_id="rowan", named=True, account="")
    regent = Session(player_id="regent", named=True, account="kingdom")
    regent.rank = "owner"
    SESSIONS["rowan"], SESSIONS["regent"] = rowan, regent
    save_character(rowan)
    save_character(regent)
    return SqlMembershipStore()


# --- the contract: every MembershipStore must obey these -------------------------------


@pytest.fixture(params=["memory", "sql"])
def store(request):
    if request.param == "memory":
        return InMemoryMembershipStore({"rowan": ("", "player"), "regent": ("kingdom", "owner")})
    return _sql_world()


def test_an_unknown_character_has_no_account(store):
    assert store.account_of("nobody_here") is None


def test_a_known_character_reports_its_account(store):
    assert store.account_of("rowan") == ""  # exists, not yet on an account
    assert store.account_of("regent") == "kingdom"


def test_set_account_links_an_existing_character(store):
    assert store.set_account("rowan", "matlabs") is True
    assert store.account_of("rowan") == "matlabs"


def test_set_account_on_a_missing_character_is_refused(store):
    assert store.set_account("ghost", "matlabs") is False
    assert store.account_of("ghost") is None


def test_retire_v1_moves_the_character_onto_the_new_account(store):
    store.retire_v1_and_set_account("rowan", "newco")
    assert store.account_of("rowan") == "newco"


def test_has_owner_sees_only_an_owner_on_that_account(store):
    assert store.has_owner("kingdom") is True  # regent is owner
    assert store.has_owner("matlabs") is False  # nobody there


def test_both_adapters_satisfy_the_port():
    assert isinstance(InMemoryMembershipStore(), MembershipStore)
    assert isinstance(SqlMembershipStore(), MembershipStore)


def test_the_in_memory_store_defensively_ignores_retire_on_a_missing_character():
    # The port's retire_v1 assumes the caller confirmed the character exists (the SQL adapter
    # asserts it); the in-memory adapter is defensive and no-ops rather than raising.
    seats = InMemoryMembershipStore({"rowan": ("", "player")})
    seats.retire_v1_and_set_account("ghost", "newco")
    assert seats.account_of("ghost") is None


# --- the domain functions run over injected stores, no database touched ----------------


def test_adopt_runs_on_an_injected_membership_store():
    from kernel.world.accounts import adopt  # noqa: PLC0415

    mem = InMemoryMembershipStore({"rowan": ("", "player")})
    assert "rowan now belongs to matlabs" in adopt("rowan", "matlabs", membership=mem)
    assert mem.account_of("rowan") == "matlabs"
    assert "No saved character" in adopt("ghost", "matlabs", membership=mem)


def test_account_has_owner_runs_on_an_injected_membership_store():
    from kernel.world.accounts import account_has_owner  # noqa: PLC0415

    mem = InMemoryMembershipStore({"regent": ("kingdom", "owner"), "peon": ("kingdom", "player")})
    assert account_has_owner("kingdom", membership=mem) is True
    assert account_has_owner("empty", membership=mem) is False


def test_inspect_login_runs_on_injected_credential_and_membership_stores():
    """The full login verdict over pure in-memory stores: account exists, password matches (crypto
    still runs), and the character is seated on that account -- no database at all."""
    import kernel.world.accounts as acc  # noqa: PLC0415
    from kernel.world.accounts import inspect_login  # noqa: PLC0415

    salt = b"\x02" * 16
    cred = InMemoryAccountCredentialStore()
    cred.create("matlabs", salt.hex(), acc._hash_secret("swordfish", salt))
    seats = InMemoryMembershipStore({"rowan": ("matlabs", "player")})

    assert inspect_login("rowan", "matlabs", "swordfish", store=cred, membership=seats) is True
    assert inspect_login("rowan", "matlabs", "wrong", store=cred, membership=seats) is False
    assert inspect_login("stranger", "matlabs", "swordfish", store=cred, membership=seats) is False
    assert inspect_login("rowan", "nosuch", "swordfish", store=cred, membership=seats) is False
