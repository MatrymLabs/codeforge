"""CARD: applied_once -- the durable exactly-once contract, consumed from the Hardware Store.

VENDORED from the Matrym Labs Hardware Store: part `applied-once` (PRT-0007). This is a consumed
Part, not repo-original code. Keep it in sync with the catalogued Part and re-vendor when the Part
changes; its canonical contract tests and mutation evidence live in the Store.

ONLY THE CONTRACT IS VENDORED, and that is the whole point of this adoption.

The Store also ships a reference implementation backed by raw sqlite3. This engine does not consume
it, because `kernel/world/reward_ledger.py` already satisfies this contract using SQLAlchemy and the
engine's own archive: driven this session, all eight of the Part's contract tests pass against it
unchanged. Vendoring the reference implementation would add a second persistence mechanism to gain
a property the engine already has.

So what is consumed is the CONTRACT and its TESTS, which is the more valuable half. The engine
declares that its ledger satisfies `AppliedOnce` and proves it by running the Part's own contract
suite in `tests/test_reward_ledger_conforms.py`. That claim is falsifiable: if the ledger drifts
from the contract, those tests fail here, in this repository, on every `make check`.

PRT-0007 was extracted from two independent implementations, this engine's `reward_ledger` and
saas-starter's `WebhookEvent`, which built the same mechanism without knowing about each other.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class KeyRefused(ValueError):  # noqa: N818
    """Raised when a key cannot name a record that can later be looked up."""


@runtime_checkable
class AppliedOnce(Protocol):
    """The minimal durable exactly-once record surface."""

    def seen(self, key: str) -> bool:
        """Return whether ``key`` has already been claimed.

        This read is not a guard and may be stale under a race. It raises ``KeyRefused`` for an
        empty key.
        """
        ...

    def claim(self, key: str) -> bool:
        """Atomically record ``key`` if absent.

        Return True only for the caller that created the durable record. Return False when the
        record already exists. It raises ``KeyRefused`` for an empty key.
        """
        ...
