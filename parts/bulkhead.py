"""CARD: bulkhead -- bound concurrent work so one slow dependency cannot sink the whole ship.

Named for a ship's watertight compartments. A `Bulkhead` caps how many operations run through a
section AT ONCE, so a flood backed up behind one slow or failing dependency is contained in its own
compartment instead of consuming every worker. Fail-fast: when the compartment is full a new entrant
is rejected immediately (`BulkheadFull`) rather than piling up unbounded and exhausting resources.
This is the standard bulkhead isolation pattern (Hystrix / resilience4j), reimplemented from the
concept -- no code copied.

Thread-safe by design, unlike its single-threaded shelf-mates: a bulkhead only means something where
work runs CONCURRENTLY, so it guards its counter with a lock. Its natural home is the threaded TCP
gateway (cap concurrent command handlers so a connection flood cannot exhaust the pool) or any
worker-pool / thread fan-out. It composes with the rest of the resilience shelf: rate-limit the
arrival rate (token-bucket), bound the in-flight count (bulkhead), fail fast on a dead dependency
(circuit-breaker), retry the transient failures (retry) within a time budget (deadline).

Provenance: independently_implemented_pattern (bulkhead isolation). No code copied.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class BulkheadError(ValueError):
    """A bulkhead was built with an invalid limit. Fails loud at construction."""


class BulkheadFull(Exception):
    """A slot was requested but the compartment is full. Fail-fast rejection; do not run the op."""


class Bulkhead:
    """Admit at most `limit` concurrent operations through a section; reject the rest fast with
    `BulkheadFull`. Thread-safe: the active count is guarded by a lock, so the cap holds under
    contention. A slot is always released, even if the guarded work raises."""

    def __init__(self, limit: int) -> None:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise BulkheadError(f"limit must be an int, got {limit!r}")
        if limit < 1:
            raise BulkheadError(f"limit must be >= 1, got {limit}")
        self._limit = limit
        self._lock = threading.Lock()
        self._active = 0

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def active(self) -> int:
        """How many operations are in the compartment right now."""
        with self._lock:
            return self._active

    @property
    def available(self) -> int:
        """How many more may enter before the compartment is full."""
        with self._lock:
            return self._limit - self._active

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Hold one slot for the duration of the block, or raise `BulkheadFull` if none is free.
        The slot is released on exit even if the block raises (capacity is never leaked)."""
        with self._lock:
            if self._active >= self._limit:
                raise BulkheadFull(f"bulkhead full ({self._active}/{self._limit})")
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    def run[T](self, fn: Callable[[], T]) -> T:
        """Run `fn` in a slot; raise `BulkheadFull` immediately if the compartment is full."""
        with self.slot():
            return fn()
