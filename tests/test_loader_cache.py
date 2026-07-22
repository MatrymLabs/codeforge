"""Test twin for parts/shelf/loader_cache.py -- the shared mtime-guarded parse-once cache.

Acceptance: parse once, reuse until the file changes. Refusal: a bad parse fails loud
every call and never poisons the cache. These are the invariants every customer (the
Hardware Store catalog, the classification registry) relies on.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from parts.shelf import loader_cache


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "data.txt"
    path.write_text(text)
    return path


def _bump_mtime(path: Path) -> None:
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_parses_once_and_returns_the_same_object(tmp_path: Path) -> None:
    calls = {"n": 0}

    def parse(p: Path) -> list[str]:
        calls["n"] += 1
        return p.read_text().split()

    path = _write(tmp_path, "a b c")
    first = loader_cache.load_cached(path, parse)
    second = loader_cache.load_cached(path, parse)
    assert first is second  # same object -> not re-parsed
    assert calls["n"] == 1  # parse ran exactly once


def test_an_on_disk_edit_invalidates_the_cache(tmp_path: Path) -> None:
    path = _write(tmp_path, "old")
    assert loader_cache.load_cached(path, lambda p: p.read_text()) == "old"
    path.write_text("new")
    _bump_mtime(path)  # guarantee a fresh mtime even if writes land in the same tick
    assert loader_cache.load_cached(path, lambda p: p.read_text()) == "new"


def test_a_raising_parse_is_never_cached(tmp_path: Path) -> None:
    path = _write(tmp_path, "boom")

    def parse(p: Path) -> str:
        raise ValueError("bad data")

    with pytest.raises(ValueError, match="bad data"):
        loader_cache.load_cached(path, parse)
    # The failure did not poison the cache: it still fails loud on the next call.
    with pytest.raises(ValueError, match="bad data"):
        loader_cache.load_cached(path, parse)


def test_clear_drops_the_cache(tmp_path: Path) -> None:
    calls = {"n": 0}

    def parse(p: Path) -> str:
        calls["n"] += 1
        return p.read_text()

    path = _write(tmp_path, "x")
    loader_cache.load_cached(path, parse)
    loader_cache.clear()
    loader_cache.load_cached(path, parse)  # cache empty -> parses again
    assert calls["n"] == 2
