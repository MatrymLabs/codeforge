"""Test twin for kernel/shelf/cache_aside.py: the cache-aside (TTL) cache.

Acceptance AND refusal cases. TTL expiry is tested deterministically with a fake clock (never a
real sleep). Hostile cases: an expired entry, an exact-boundary expiry, a loader that raises (must
not cache a failure), and a non-positive TTL.
"""

from __future__ import annotations

import pytest

from kernel.shelf.cache_aside import CacheAside, CacheError


class _Clock:
    """A controllable monotonic clock for deterministic TTL tests."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class _Loader:
    """A loader whose call count is observable, to prove hits avoid the source."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> int:
        self.calls += 1
        return self.value


# --- Acceptance ------------------------------------------------------------------------------


def test_miss_loads_then_hit_serves_from_cache() -> None:
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=10, clock=_Clock())
    load = _Loader(42)
    assert cache.get("k", load) == 42  # miss -> loads
    assert cache.get("k", load) == 42  # hit -> cached, loader NOT called again
    assert load.calls == 1
    assert cache.hits == 1 and cache.misses == 1


def test_expiry_reloads_from_source() -> None:
    clock = _Clock()
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=10, clock=clock)
    load = _Loader(1)
    cache.get("k", load)
    clock.advance(9.9)
    cache.get("k", load)  # still fresh -> hit
    assert load.calls == 1
    clock.advance(0.2)  # now 10.1s elapsed, past the 10s TTL
    cache.get("k", load)  # expired -> reload
    assert load.calls == 2


def test_exact_ttl_boundary_is_expired() -> None:
    # expires_at is strict (> now): at exactly the TTL, the entry is treated as expired and reloads.
    clock = _Clock()
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=5, clock=clock)
    load = _Loader(1)
    cache.get("k", load)
    clock.advance(5.0)  # exactly at expiry
    cache.get("k", load)
    assert load.calls == 2


def test_invalidate_evicts_now() -> None:
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=100, clock=_Clock())
    load = _Loader(7)
    cache.get("k", load)
    assert cache.invalidate("k") is True
    assert cache.invalidate("k") is False  # already gone
    cache.get("k", load)  # a change was signalled -> reload despite the long TTL
    assert load.calls == 2


def test_clear_empties_but_keeps_stats() -> None:
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=100, clock=_Clock())
    cache.get("a", _Loader(1))
    cache.get("b", _Loader(2))
    assert cache.size == 2
    cache.clear()
    assert cache.size == 0
    assert cache.misses == 2  # stats survive a clear


def test_is_cached_reflects_freshness() -> None:
    clock = _Clock()
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=10, clock=clock)
    assert cache.is_cached("k") is False
    cache.get("k", _Loader(1))
    assert cache.is_cached("k") is True
    clock.advance(11)
    assert cache.is_cached("k") is False  # past TTL


def test_hit_rate() -> None:
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=100, clock=_Clock())
    assert cache.hit_rate == 0.0  # no reads yet
    load = _Loader(1)
    cache.get("k", load)  # miss
    cache.get("k", load)  # hit
    cache.get("k", load)  # hit
    assert cache.hit_rate == pytest.approx(2 / 3)


# --- Refusal ---------------------------------------------------------------------------------


def test_failed_loader_is_not_cached() -> None:
    cache: CacheAside[str, int] = CacheAside(ttl_seconds=100, clock=_Clock())
    calls = {"n": 0}

    def flaky() -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("source down")
        return 5

    with pytest.raises(RuntimeError):
        cache.get("k", flaky)
    assert cache.is_cached("k") is False  # a failed load stored nothing
    assert cache.get("k", flaky) == 5  # a retry hits the source again and succeeds
    assert calls["n"] == 2


@pytest.mark.parametrize("ttl", [0, -1, -0.5])
def test_nonpositive_ttl_refused(ttl: float) -> None:
    with pytest.raises(CacheError):
        CacheAside(ttl_seconds=ttl, clock=_Clock())


def test_bool_ttl_refused() -> None:
    # bool is an int subtype (mypy accepts it), but True is not a valid TTL at runtime.
    with pytest.raises(CacheError):
        CacheAside(ttl_seconds=True, clock=_Clock())
