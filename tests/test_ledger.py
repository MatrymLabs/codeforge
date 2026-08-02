"""Test twin for kernel/ledger.py: the double-entry ledger.

Acceptance AND refusal cases. The headline guarantee -- money is conserved, total debits always
equal total credits -- is pinned here on worked examples and, exhaustively, by the Hypothesis
property suite in test_ledger_properties.py. Hostile cases: a deliberately-induced double-spend
(the same idempotency key replayed), an overdraft on a guarded account, a self-transfer, a
duplicate transfer id, and non-integer/negative amounts.
"""

from __future__ import annotations

import pytest

from kernel.ledger import Account, Ledger, LedgerError, Transfer


def _funded_ledger() -> Ledger:
    """A ledger with a house account credited 1000 and an empty wallet, ready to transfer."""
    ledger = Ledger()
    ledger.open_account("house")
    ledger.open_account("wallet", debits_must_not_exceed_credits=True)
    # Seed: the house grants 1000 to the wallet (house debits, wallet credits).
    ledger.post_transfer("seed", "house", "wallet", 1000)
    return ledger


# --- Acceptance: a transfer moves money and keeps the books balanced -------------------------


def test_transfer_posts_equal_debit_and_credit() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    t = ledger.post_transfer("t1", "a", "b", 250)
    assert isinstance(t, Transfer)
    assert ledger.account("a").debits_posted == 250
    assert ledger.account("b").credits_posted == 250
    # Conservation: total debits == total credits, by construction.
    assert ledger.total_debits() == ledger.total_credits() == 250
    ledger.assert_balanced()


def test_transfer_log_is_append_only_and_ordered() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    ledger.post_transfer("t1", "a", "b", 10)
    ledger.post_transfer("t2", "b", "a", 4)
    log = ledger.transfers()
    assert [t.id for t in log] == ["t1", "t2"]
    # The returned log is a snapshot; mutating it cannot corrupt the ledger.
    assert isinstance(log, tuple)


def test_balance_is_debits_minus_credits() -> None:
    ledger = _funded_ledger()
    # wallet was credited 1000 (its balance is credits-heavy: debits 0 - credits 1000).
    assert ledger.balance("wallet") == -1000
    # spend 300 from the wallet to a shop (wallet debits 300).
    ledger.open_account("shop")
    ledger.post_transfer("buy", "wallet", "shop", 300)
    assert ledger.account("wallet").debits_posted == 300
    assert ledger.balance("wallet") == 300 - 1000
    ledger.assert_balanced()


# --- Acceptance: idempotency makes a retry safe (the deliberately-induced double-spend) -------


def test_idempotent_retry_does_not_double_spend() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    first = ledger.post_transfer("t1", "a", "b", 100, idempotency_key="req-1")
    # The client never heard back and retries the SAME request under the SAME key.
    replay = ledger.post_transfer("t1", "a", "b", 100, idempotency_key="req-1")
    assert replay == first  # the original transfer, replayed
    # Money moved exactly ONCE, not twice.
    assert ledger.account("a").debits_posted == 100
    assert ledger.account("b").credits_posted == 100
    assert len(ledger.transfers()) == 1


def test_same_key_different_amount_is_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    ledger.post_transfer("t1", "a", "b", 100, idempotency_key="req-1")
    with pytest.raises(Exception):  # noqa: B017 - IdempotencyConflict (a subclass of ValueError)
        ledger.post_transfer("t2", "a", "b", 250, idempotency_key="req-1")
    # The refused retry moved nothing extra.
    assert ledger.account("a").debits_posted == 100


# --- Refusal: every rule is enforced before any balance moves --------------------------------


def test_unknown_account_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    with pytest.raises(LedgerError):
        ledger.post_transfer("t1", "a", "nope", 10)
    with pytest.raises(LedgerError):
        ledger.post_transfer("t2", "ghost", "a", 10)
    # Nothing moved: the known account is untouched.
    assert ledger.account("a").debits_posted == 0
    assert ledger.account("a").credits_posted == 0


def test_nonpositive_amount_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    for bad in (0, -5):
        with pytest.raises(LedgerError):
            ledger.post_transfer("t", "a", "b", bad)


def test_non_integer_amount_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    # Money is not a float, and a bool is not an amount.
    with pytest.raises(LedgerError):
        ledger.post_transfer("t", "a", "b", 10.0)  # type: ignore[arg-type]
    with pytest.raises(LedgerError):
        # bool is an int subtype (mypy accepts it), but a bool is not a monetary amount at runtime.
        ledger.post_transfer("t", "a", "b", True)


def test_self_transfer_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    with pytest.raises(LedgerError):
        ledger.post_transfer("t", "a", "a", 10)


def test_duplicate_transfer_id_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    ledger.post_transfer("t1", "a", "b", 10)
    with pytest.raises(LedgerError):
        ledger.post_transfer("t1", "a", "b", 10)  # same id, no idempotency key
    assert len(ledger.transfers()) == 1


def test_overdraft_on_guarded_account_refused() -> None:
    ledger = _funded_ledger()  # wallet has 1000 credited, debits_must_not_exceed_credits
    ledger.open_account("shop")
    # Spending up to the credited balance is fine.
    ledger.post_transfer("ok", "wallet", "shop", 1000)
    # One over the balance is refused (the wallet may not go overdrawn).
    with pytest.raises(LedgerError):
        ledger.post_transfer("over", "wallet", "shop", 1)
    assert ledger.account("wallet").debits_posted == 1000
    ledger.assert_balanced()


def test_open_account_rules() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    with pytest.raises(LedgerError):
        ledger.open_account("a")  # duplicate
    with pytest.raises(LedgerError):
        ledger.open_account("   ")  # blank
    with pytest.raises(LedgerError):
        ledger.account("missing")  # unknown lookup


def test_transfer_is_immutable() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    t = ledger.post_transfer("t1", "a", "b", 10)
    with pytest.raises(Exception):  # noqa: B017 - frozen dataclass raises FrozenInstanceError
        t.amount = 999  # type: ignore[misc]


def test_blank_transfer_id_refused() -> None:
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    with pytest.raises(LedgerError):
        ledger.post_transfer("  ", "a", "b", 10)


def test_account_balance_property() -> None:
    acct = Account(id="x", debits_posted=30, credits_posted=12)
    assert acct.balance == 18


def test_credit_side_overdraft_guard_refused() -> None:
    # A mirror of the debit guard: an account that may not be credited past its debits.
    ledger = Ledger()
    ledger.open_account("source")
    ledger.open_account("bounded", credits_must_not_exceed_debits=True)
    # Give 'bounded' 100 debits first (source credits it via a reverse posting).
    ledger.post_transfer("fund", "bounded", "source", 100)  # bounded.debits_posted = 100
    # Crediting it up to its debits is fine...
    ledger.post_transfer("ok", "source", "bounded", 100)  # bounded.credits_posted = 100
    # ...one over its debits is refused.
    with pytest.raises(LedgerError):
        ledger.post_transfer("over", "source", "bounded", 1)
    ledger.assert_balanced()


def test_assert_balanced_catches_a_corrupted_book() -> None:
    # The invariant holds by construction; this proves the defensive check would catch a violation
    # (e.g. a bug reaching in and mutating a posted total out of band).
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    ledger.post_transfer("t1", "a", "b", 10)
    ledger.assert_balanced()  # balanced
    ledger.account("a").debits_posted += 5  # simulate out-of-band corruption
    with pytest.raises(LedgerError):
        ledger.assert_balanced()
