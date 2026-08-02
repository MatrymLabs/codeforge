"""CARD: cache_aside -- a cache-aside (lazy) cache with a TTL and explicit invalidation.

The caching pattern behind "read it fast, but never serve a stale answer for too long." On a read,
look in the cache: on a hit within its time-to-live, return the cached value; on a miss or an
expired entry, load it from the source of truth, store it with a fresh expiry, and return it. That
is the documented cache-aside (lazy-loading) pattern used with Redis and every application cache.

The discipline this part enforces (the ship's optimization ethos: "cache only when invalidation is
clear"): every cached value has a **TTL** so staleness is bounded by time, AND an **explicit
`invalidate(key)`** so a known change evicts immediately rather than waiting out the clock. A cache
without a clear invalidation story is a correctness bug in waiting; this one makes both levers
first-class.

Design notes:
- **Injectable clock.** The clock is a seam (`clock=time.monotonic` by default); tests pass a fake
  clock to make TTL expiry deterministic, never a real `sleep`.
- **A failed load is never cached.** If the loader raises, nothing is stored, so a transient source
  error does not become a cached failure -- the next read retries the source.
- **Hit/miss stats** are tracked so the cache's value is measurable, not assumed (an unmeasured
  cache can be pure overhead).

Fail-loud: a non-positive TTL is refused at construction. In-memory and single-process; a networked
deployment maps the same contract onto Redis (`GET` then `SETEX`, with `DEL` for invalidation).

Provenance: original implementation of the publicly documented cache-aside pattern. No code copied;
not affiliated with Redis or any cache product.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


class CacheError(ValueError):
    """A refused cache configuration (a non-positive TTL): fail loud rather than cache forever."""


@dataclass
class CacheAside[K, V]:
    """A lazy cache: values load on a miss and expire after `ttl_seconds`; changes invalidate.

    In-memory and single-process. A networked deployment maps the same contract onto Redis
    (`GET` -> on miss load + `SETEX ttl`, and `DEL` for `invalidate`). The clock is injectable so
    TTL behaviour is tested deterministically without sleeping.
    """

    ttl_seconds: float
    clock: Callable[[], float] = time.monotonic
    _entries: dict[K, tuple[V, float]] = field(default_factory=dict)  # key -> (value, expires_at)
    _hits: int = 0
    _misses: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.ttl_seconds, (int, float)) or isinstance(self.ttl_seconds, bool):
            raise CacheError(f"ttl_seconds must be a number, got {self.ttl_seconds!r}")
        if self.ttl_seconds <= 0:
            raise CacheError(f"ttl_seconds must be > 0, got {self.ttl_seconds}")

    def get(self, key: K, loader: Callable[[], V]) -> V:
        """Return the value for `key`, from the cache if fresh, else via `loader` (then cached).

        A hit within the TTL returns the cached value without calling `loader`. A miss or an expired
        entry calls `loader`, stores the result with a fresh expiry, and returns it. If `loader`
        raises, nothing is stored and the exception propagates (a failed load is never cached).
        """
        now = self.clock()
        entry = self._entries.get(key)
        if entry is not None and entry[1] > now:  # a hit, still within its TTL
            self._hits += 1
            return entry[0]
        self._misses += 1
        value = loader()  # a raise here stores nothing; the next read retries the source
        self._entries[key] = (value, now + self.ttl_seconds)
        return value

    def is_cached(self, key: K) -> bool:
        """Whether `key` has a fresh value cached (within its TTL). A read-only check, no load."""
        entry = self._entries.get(key)
        return entry is not None and entry[1] > self.clock()

    def invalidate(self, key: K) -> bool:
        """Evict `key` now (a known change should not wait out the TTL). Returns whether present."""
        return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        """Evict everything (e.g. after a bulk change). Stats are preserved."""
        self._entries.clear()

    @property
    def hits(self) -> int:
        """How many reads were served from the cache."""
        return self._hits

    @property
    def misses(self) -> int:
        """How many reads had to load from the source (a miss or an expiry)."""
        return self._misses

    @property
    def hit_rate(self) -> float:
        """Fraction of reads served from the cache (0.0 when there have been no reads yet)."""
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    @property
    def size(self) -> int:
        """How many entries are held (including any past their TTL but not yet evicted)."""
        return len(self._entries)
