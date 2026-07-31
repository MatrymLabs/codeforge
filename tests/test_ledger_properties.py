"""Property tests: the double-entry ledger's conservation invariant under any transfer sequence.

The ledger's headline guarantee is that money is conserved: across the whole book, the sum of all
debits always equals the sum of all credits, no matter what sequence of transfers is posted. A
single worked example proves it once; Hypothesis proves it across hundreds of generated sequences,
including refused transfers (which must leave the books exactly as they were). This is the
correctness-under-adversity evidence a double-entry ledger exists to provide.

Marked `property`, so it runs under `make property`, not the fast `make check` gate.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from parts.ledger import Ledger, LedgerError

_ACCOUNTS = ["a", "b", "c", "d"]

# A transfer request: (debit, credit, amount). Amounts include 0 and negatives on purpose, so the
# property also exercises the refusal path (a bad request must not disturb the invariant).
_transfer = st.tuples(
    st.sampled_from(_ACCOUNTS),
    st.sampled_from(_ACCOUNTS),
    st.integers(min_value=-50, max_value=500),
)


@pytest.mark.property
@settings(max_examples=300)
@given(requests=st.lists(_transfer, max_size=40))
def test_debits_always_equal_credits(requests: list[tuple[str, str, int]]) -> None:
    ledger = Ledger()
    for name in _ACCOUNTS:
        ledger.open_account(name)
    posted = 0
    for i, (debit, credit, amount) in enumerate(requests):
        try:
            ledger.post_transfer(f"t{i}", debit, credit, amount)
            posted += 1
        except LedgerError:
            pass  # a refused transfer is expected for bad input; it must change nothing
        # The invariant holds after EVERY step, accepted or refused.
        assert ledger.total_debits() == ledger.total_credits()
    ledger.assert_balanced()
    assert len(ledger.transfers()) == posted


@pytest.mark.property
@settings(max_examples=200)
@given(
    amount=st.integers(min_value=1, max_value=1000),
    retries=st.integers(min_value=1, max_value=8),
)
def test_idempotent_retries_apply_exactly_once(amount: int, retries: int) -> None:
    # A transfer replayed under one idempotency key any number of times applies exactly once.
    ledger = Ledger()
    ledger.open_account("a")
    ledger.open_account("b")
    for _ in range(retries):
        ledger.post_transfer("t1", "a", "b", amount, idempotency_key="req")
    assert ledger.account("a").debits_posted == amount
    assert ledger.account("b").credits_posted == amount
    assert len(ledger.transfers()) == 1
    ledger.assert_balanced()
