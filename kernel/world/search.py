"""CARD: search -- index the world's rooms, items, and NPCs and answer `search` by relevance.

Adopts SQLite FTS5 (stdlib sqlite3, BM25 ranking) as the world search index over the canonical
WORLD / ITEMS / NPCS registries (R&D Technology Admission T-AP-05; measured 80-129x over a linear
scan, relevance-gated by a golden set). If FTS5 is not compiled into the host sqlite, it degrades to
a substring scan so the verb always answers (ADR-0010 fallback ethos). The index builds lazily on
the first search and rebuilds when the world's content changes (a membership sentinel).

Scope: v1 searches all PUBLIC world content (rooms, items, NPCs) - this is a knowledge/codex search
over game content, not per-player private state, so no authorization boundary is crossed. A
per-player visibility filter (discovered rooms) is a future enhancement once such a model exists.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from kernel.world.items import ITEMS
from kernel.world.npcs import NPCS
from kernel.world.world import WORLD

_TOKEN = re.compile(r"[a-z0-9]+")
_LIMIT = 8

# how each doc kind is labelled in the rendered result
_KIND_LABEL = {"room": "place", "item": "item", "npc": "being"}


@dataclass(frozen=True)
class Found:
    """A search result: a typed doc id, its display name, and a score (higher = better)."""

    doc_id: str  # "room:<label>" | "item:<label>" | "npc:<label>"
    name: str
    score: float


def _corpus() -> list[tuple[str, str, str]]:
    """(doc_id, display_name, body) for every searchable world thing."""
    rows: list[tuple[str, str, str]] = []
    for label, room in WORLD.items():
        name = str(room.get("name", label))
        rows.append((f"room:{label}", name, f"{name} {room.get('desc', '')}"))
    for label, item in ITEMS.items():
        name = str(item.get("name", label))
        keywords = " ".join(item.get("keywords", []))
        rows.append((f"item:{label}", name, f"{name} {keywords} {item.get('lore', '')}"))
    for label, npc in NPCS.items():
        name = str(npc.get("name", label))
        keywords = " ".join(npc.get("keywords", []))
        rows.append((f"npc:{label}", name, f"{name} {keywords}"))
    return rows


def _tokens(query: str) -> list[str]:
    """Alphanumeric tokens of a free-text query (also the injection-safe MATCH source)."""
    return _TOKEN.findall(query.lower())


class _WorldIndex:
    """An FTS5 (or substring-fallback) index over a fixed world corpus."""

    def __init__(self, corpus: list[tuple[str, str, str]], *, allow_fts: bool = True) -> None:
        self._names = {doc_id: name for doc_id, name, _ in corpus}
        self._con = sqlite3.connect(":memory:")
        self._closed = False
        self._fts = allow_fts
        try:
            if not allow_fts:
                raise sqlite3.OperationalError(  # noqa: TRY003, TRY301
                    "fts disabled"
                )  # forced substring path (tests)
            self._con.execute("CREATE VIRTUAL TABLE docs USING fts5(doc_id UNINDEXED, body)")
        except sqlite3.OperationalError:  # FTS5 not compiled in -> substring fallback
            self._fts = False
            self._con.execute("CREATE TABLE docs (doc_id TEXT, body TEXT)")
        self._con.executemany(
            "INSERT INTO docs(doc_id, body) VALUES (?, ?)", [(d, b) for d, _, b in corpus]
        )

    def search(self, query: str, limit: int = _LIMIT) -> list[Found]:
        tokens = _tokens(query)
        if not tokens:
            return []
        if self._fts:
            # OR of the alnum tokens: a parameterized MATCH value, so no injection surface.
            sql = (
                "SELECT doc_id, bm25(docs) FROM docs WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT ?"
            )
            rows = self._con.execute(sql, (" OR ".join(tokens), limit)).fetchall()
            # sqlite bm25 is lower-is-better; negate so a higher score is a better hit.
            return [
                Found(doc_id, self._names.get(doc_id, doc_id), -score) for doc_id, score in rows
            ]
        # substring fallback: rank by how many query tokens appear in the body.
        found: list[Found] = []
        for doc_id, body in self._con.execute("SELECT doc_id, body FROM docs").fetchall():
            low = body.lower()
            matched = sum(1 for t in tokens if t in low)
            if matched:
                found.append(Found(doc_id, self._names.get(doc_id, doc_id), float(matched)))
        found.sort(key=lambda f: (-f.score, f.doc_id))
        return found[:limit]

    def close(self) -> None:
        """Close the in-memory SQLite connection held by the search index."""
        if not self._closed:
            self._con.close()
            self._closed = True

    def __del__(self) -> None:
        if not getattr(self, "_closed", True):
            self.close()


_index: _WorldIndex | None = None
_sentinel: tuple[int, int, int] = (-1, -1, -1)


def _get_index() -> _WorldIndex:
    """The world index, built lazily and rebuilt when the world's content count changes."""
    global _index, _sentinel  # noqa: PLW0603
    sig = (len(WORLD), len(ITEMS), len(NPCS))
    if _index is None or sig != _sentinel:
        if _index is not None:
            _index.close()
        _index = _WorldIndex(_corpus())
        _sentinel = sig
    return _index


def reset() -> None:
    """Drop the cached index (for tests or after a reseed)."""
    global _index, _sentinel  # noqa: PLW0603
    if _index is not None:
        _index.close()
    _index = None
    _sentinel = (-1, -1, -1)


def world_search(query: str) -> str:
    """CORE `search <words>`: find world rooms, items, and NPCs by relevance."""
    query = query.strip()
    if not query:
        return "Search for what? (try: search ember blade)"
    found = _get_index().search(query)
    if not found:
        return f"Nothing in the known world matches '{query}'."
    lines = [f"World search for '{query}':"]
    for hit in found:
        kind = hit.doc_id.split(":", 1)[0]
        lines.append(f"  ({_KIND_LABEL.get(kind, kind)}) {hit.name}")
    return "\n".join(lines)
