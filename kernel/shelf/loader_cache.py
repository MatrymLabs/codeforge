"""CARD: loader_cache -- parse a file once, re-read only when it changes (mtime-guarded).

The Forge's shared parse-once cache. Several parts read an immutable-within-a-run data
file (the Hardware Store catalog, the classification registry) and re-parse it on every
call -- pure duplicate work (EXP-001 measured ~426x waste on the catalog alone; the qa-gate
self-audit re-parsed the whole registry every render). This part is the ONE place that
pattern lives: hand it a path and a parse function, and it parses once, returning the cached
value until the file's mtime changes on disk.

Discipline (inherited from EXP-001): a parse that raises is never cached, so a broken edit
fails loud on every call and can never poison the cache. The caller owns the missing-file
decision (check `exists()` first); this caches only a successful parse of a present file.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

# Resolved path -> (mtime_ns, parsed value). Module-level, so the cache spans the process.
# Cleared per-test by conftest so a tmp file reused across tests can never serve stale data.
_CACHE: dict[Path, tuple[int, object]] = {}


def load_cached[T](path: Path, parse: Callable[[Path], T]) -> T:
    """Return `parse(path)`, cached by the file's mtime; re-parse only when the file changes.

    Inputs: an existing file path, and a pure parse function of that path.
    Output: the parsed value (the SAME object across calls while the file is unchanged).
    A parse that raises propagates and is not cached (a bad edit fails loud every call).
    """
    key = path.resolve()
    mtime_ns = key.stat().st_mtime_ns  # raises if the file is gone -- caller checks first
    cached = _CACHE.get(key)
    if cached is not None and cached[0] == mtime_ns:
        return cast(T, cached[1])
    value = parse(path)  # a raise here never reaches the store below -> never cached
    _CACHE[key] = (mtime_ns, value)
    return value


def clear() -> None:
    """Drop the whole cache (for tests, or to force a reload)."""
    _CACHE.clear()
