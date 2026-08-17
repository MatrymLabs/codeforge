"""CARD: idempotency -- an idempotency-key store: make a retried operation safe to repeat.

The reusable core behind "the client sent the same request twice" -- a network retry, a
double-click, an at-least-once queue redelivery. Stripe's model, reconstructed from its public
docs: the caller tags an operation with an idempotency KEY and a FINGERPRINT of the request. The
store runs the operation at most once per key and remembers its result:

- a first call runs the operation, stores the result under (key, fingerprint), returns it (fresh);
- a replay with the SAME key and fingerprint returns the stored result WITHOUT re-running it;
- a replay with the same key but a DIFFERENT fingerprint is a conflict -- the same key must never
  stand for two different requests -- and is refused, loudly.

Only a *successful* result is remembered: if the operation raises, nothing is stored, so a genuine
retry runs it again (a half-applied failure is never cached as success). It stores results; it
does not perform side effects of its own. In-memory here; the identical contract fronts a durable
table with a UNIQUE index on the key in a networked service.

Provenance: original implementation of the publicly documented Stripe idempotency-key pattern
(the `Idempotency-Key` header; a response keyed by (account, key); a mismatched body under the
same key rejected). No code copied; not affiliated with or endorsed by Stripe.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


class IdempotencyError(ValueError):
    """A malformed idempotency request (empty key or fingerprint): fail loud, store nothing."""


class IdempotencyConflict(IdempotencyError):  # noqa: N818
    """The same key was reused for a different request fingerprint: refuse, never return the wrong
    result. The key is the client's promise that two calls are the same call; a changed fingerprint
    breaks that promise."""


@dataclass(frozen=True)
class Outcome[T]:
    """The result of a guarded operation, and whether it was replayed from the store."""

    result: T
    replayed: bool  # True -> returned a stored result; the operation did NOT run this time


@dataclass
class IdempotencyStore[T]:
    """Remember the result of an operation under an idempotency key, so a retry is safe.

    Single-process and in-memory: the engine tick is single-threaded, so no lock is taken. A
    networked deployment fronts this same contract with a durable, UNIQUE-indexed table (and a row
    lock or an upsert) to make the check-run-store atomic across processes -- see the ledger design
    doc. Keys are exact and case-sensitive ("Key" and "key" are different promises).
    """

    _entries: dict[str, tuple[str, T]] = field(default_factory=dict)  # key -> (fingerprint, result)

    def seen(self, key: str) -> bool:
        """Whether a result is already stored under `key`."""
        return key in self._entries

    def remember(self, key: str, fingerprint: str, factory: Callable[[], T]) -> Outcome[T]:
        """Run `factory` at most once per `key`, returning its result.

        A first (key, fingerprint) runs `factory`, stores the result, and returns it (replayed
        False). A repeat with the same key and fingerprint returns the stored result without
        running `factory` (replayed True). The same key with a different fingerprint raises
        `IdempotencyConflict`. If `factory` raises, nothing is stored and the exception propagates,
        so a real retry runs it again. Empty key or fingerprint raises `IdempotencyError`.
        """
        if not key or not key.strip():
            raise IdempotencyError("idempotency key must be a non-empty string")  # noqa: TRY003
        if not fingerprint or not fingerprint.strip():
            raise IdempotencyError("request fingerprint must be a non-empty string")  # noqa: TRY003

        existing = self._entries.get(key)
        if existing is not None:
            stored_fingerprint, stored_result = existing
            if stored_fingerprint != fingerprint:
                raise IdempotencyConflict(  # noqa: TRY003
                    f"idempotency key {key!r} was already used for a different request "
                    "(fingerprint mismatch); reusing a key for a changed request is refused"
                )
            return Outcome(result=stored_result, replayed=True)

        result = factory()  # only reached for a new key; a raise here stores nothing
        self._entries[key] = (fingerprint, result)
        return Outcome(result=result, replayed=False)
