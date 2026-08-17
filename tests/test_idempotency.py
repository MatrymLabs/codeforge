"""Test twin for kernel/shelf/idempotency.py: the idempotency-key store (Stripe semantics).

Acceptance AND refusal cases, with hostile data: case-sensitive keys, a mismatched fingerprint
under a reused key, empty inputs, and a factory that raises (so a retry re-runs, never caches a
half-applied failure as success).
"""

from __future__ import annotations

import pytest

from kernel.shelf.idempotency import (
    IdempotencyConflict,
    IdempotencyError,
    IdempotencyStore,
)


class _Counter:
    """A factory whose call count is observable, to prove an operation runs at most once."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return self.value


# --- Acceptance ------------------------------------------------------------------------------


def test_first_call_runs_and_returns_fresh() -> None:
    store: IdempotencyStore[int] = IdempotencyStore()
    make = _Counter(42)
    out = store.remember("k1", "fp", make)
    assert out.result == 42
    assert out.replayed is False
    assert make.calls == 1
    assert store.seen("k1") is True


def test_replay_returns_stored_without_rerunning() -> None:
    store: IdempotencyStore[int] = IdempotencyStore()
    make = _Counter(7)
    store.remember("k1", "fp", make)
    out2 = store.remember("k1", "fp", make)  # same key + fingerprint
    assert out2.result == 7
    assert out2.replayed is True
    assert make.calls == 1  # the operation ran ONCE, not twice


def test_distinct_keys_each_run() -> None:
    store: IdempotencyStore[int] = IdempotencyStore()
    a, b = _Counter(1), _Counter(2)
    assert store.remember("a", "fp", a).result == 1
    assert store.remember("b", "fp", b).result == 2
    assert a.calls == 1 and b.calls == 1


# --- Refusal ---------------------------------------------------------------------------------


def test_reused_key_different_fingerprint_conflicts() -> None:
    store: IdempotencyStore[int] = IdempotencyStore()
    store.remember("k1", "fingerprint-A", _Counter(1))
    with pytest.raises(IdempotencyConflict):
        store.remember("k1", "fingerprint-B", _Counter(999))


def test_keys_are_case_sensitive() -> None:
    # A hostile near-miss: "Key" and "key" are different promises, so both run independently.
    store: IdempotencyStore[int] = IdempotencyStore()
    upper, lower = _Counter(1), _Counter(2)
    store.remember("Key", "fp", upper)
    out = store.remember("key", "fp", lower)
    assert out.replayed is False
    assert lower.calls == 1


@pytest.mark.parametrize("key", ["", "   "])
def test_empty_key_refused(key: str) -> None:
    store: IdempotencyStore[int] = IdempotencyStore()
    with pytest.raises(IdempotencyError):
        store.remember(key, "fp", _Counter(1))


@pytest.mark.parametrize("fingerprint", ["", "   "])
def test_empty_fingerprint_refused(fingerprint: str) -> None:
    store: IdempotencyStore[int] = IdempotencyStore()
    with pytest.raises(IdempotencyError):
        store.remember("k1", fingerprint, _Counter(1))


def test_failed_factory_stores_nothing_so_retry_reruns() -> None:
    store: IdempotencyStore[int] = IdempotencyStore()

    calls = {"n": 0}

    def flaky() -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient failure")  # noqa: TRY003
        return 99

    # First attempt raises: nothing is cached as success.
    with pytest.raises(RuntimeError):
        store.remember("k1", "fp", flaky)
    assert store.seen("k1") is False

    # A genuine retry under the same key runs the operation again and now succeeds.
    out = store.remember("k1", "fp", flaky)
    assert out.result == 99
    assert out.replayed is False
    assert calls["n"] == 2


def test_conflict_is_a_kind_of_idempotency_error() -> None:
    # Callers may catch the broad IdempotencyError; a conflict is one of its cases.
    assert issubclass(IdempotencyConflict, IdempotencyError)
