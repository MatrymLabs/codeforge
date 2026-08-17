"""The Hardware Store's own contract tests for PRT-0007, run against this engine's ledger.

Consuming a Part usually means vendoring its implementation. Here it means the opposite and the
distinction is the point: `kernel/world/reward_ledger.py` already satisfies `applied-once` using
SQLAlchemy and the engine's archive, so vendoring the Part's raw-sqlite3 reference implementation
would add a second persistence mechanism to gain a property the engine already has.

What is consumed is the CONTRACT. This file is what makes that consumption falsifiable: if the
ledger ever drifts from `AppliedOnce`, these fail here, on `make check`, in this repository. A
citation nothing can disprove is the thing the Store exists to refuse.

The assertions are the Store's, copied unchanged from catalog/applied-once/tests/test_contract.py.
Re-vendor them when the Part changes.
"""

from __future__ import annotations

import pytest

from kernel.shelf.applied_once import AppliedOnce
from kernel.world.reward_ledger import GrantLedger


@pytest.fixture
def store() -> GrantLedger:
    return GrantLedger()


def test_the_ledger_satisfies_the_part_protocol(store: GrantLedger) -> None:
    assert isinstance(store, AppliedOnce)


def test_an_unseen_key_is_not_yet_applied(store: GrantLedger) -> None:
    assert not store.seen("evt_1234")


def test_claiming_an_unseen_key_succeeds(store: GrantLedger) -> None:
    assert store.claim("evt_1234") is True


def test_a_claimed_key_is_seen(store: GrantLedger) -> None:
    store.claim("evt_1234")
    assert store.seen("evt_1234")


def test_the_same_key_never_claims_twice(store: GrantLedger) -> None:
    assert store.claim("evt_1234") is True
    assert store.claim("evt_1234") is False
    assert store.claim("evt_1234") is False


def test_a_different_key_is_unaffected(store: GrantLedger) -> None:
    store.claim("evt_1234")
    assert not store.seen("evt_5678")
    assert store.claim("evt_5678") is True


def test_the_key_is_opaque_to_the_part(store: GrantLedger) -> None:
    """A Stripe event id and a game grant identity must behave identically."""
    assert store.claim("evt_1234") is True
    assert store.claim("hero|npc:training_dummy|4") is True
    assert store.claim("hero|npc:training_dummy|5") is True
    assert store.claim("hero|npc:training_dummy|4") is False


def test_an_empty_key_is_refused_loudly(store: GrantLedger) -> None:
    """Resolved through the MODULE, not the name imported at the top of this file.

    tests/test_reward_ledger.py calls importlib.reload, which rebinds GrantIdentityError to a new
    class object. A bare pytest.raises(GrantIdentityError) here passes alone and fails in the full
    suite, matching nothing. I wrote this warning into the CX-003 packet for Codex and then walked
    into it myself, which is the argument for the warning rather than against it.
    """
    from kernel.world import reward_ledger  # noqa: PLC0415

    for bad in ("", "   "):
        with pytest.raises(reward_ledger.GrantIdentityError):
            store.claim(bad)
        with pytest.raises(reward_ledger.GrantIdentityError):
            store.seen(bad)


def test_the_record_outlives_the_store_object(store: GrantLedger) -> None:
    """A SECOND ledger object must already know the key. The whole point of the Part."""
    assert store.claim("evt_durable") is True
    second = GrantLedger()
    assert second.seen("evt_durable")
    assert second.claim("evt_durable") is False


def test_an_opaque_key_cannot_collide_with_a_real_grant(store: GrantLedger) -> None:
    """ADDED beyond the Store's suite: the engine flattens identities, so prove the seam is safe."""
    from kernel.world.reward_ledger import claim_grant, grant_key  # noqa: PLC0415

    assert claim_grant("hero", "npc:training_dummy", 1) is True
    assert store.seen(grant_key("hero", "npc:training_dummy", 1))
    assert store.claim("hero") is True  # bare string, reserved source, no collision
    assert store.claim("hero") is False


def test_only_one_of_many_concurrent_claimants_wins() -> None:
    """ADDED, and the Store's suite needs this too.

    Sabotaging `claim` into check-then-act -- read, then write, the exact race the Part exists to
    prevent -- passed all eight of the Store's contract tests. They are single-threaded, so an
    implementation that has lost atomicity behaves identically under them.

    Atomicity is the property that distinguishes this Part from the in-memory predecessor it
    supersedes, and it was the one property the contract could not falsify. Filed against the Part.
    """
    import threading  # noqa: PLC0415

    from kernel.world.reward_ledger import claim_grant  # noqa: PLC0415

    # Warm the archive FIRST. Eight threads hitting a cold engine each run create_all and collide
    # on "table already exists", which is a real race in open_archive_session but NOT the one under
    # test here. Provoking it would make this test fail for a reason that has nothing to do with
    # the claim. Filed separately; boot happens before players connect, so it does not bite live.
    claim_grant("warmup", "npc:warmup", 1)

    wins: list[bool] = []
    lock = threading.Lock()
    start = threading.Barrier(8)

    def race() -> None:
        start.wait()
        won = claim_grant("racer", "npc:contested", 1)
        with lock:
            wins.append(won)

    threads = [threading.Thread(target=race) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert wins.count(True) == 1, f"{wins.count(True)} claimants were paid for one grant: {wins}"
    assert wins.count(False) == 7
