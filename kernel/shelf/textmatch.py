"""CARD: textmatch -- fuzzy string matching: Levenshtein distance + the nearest candidate.

A Hardware Store primitive for "did you mean ...?": how far apart are two strings, and which of a
set of candidates is closest? The edit-distance core is a small O(m*n) program -- cheap in C,
slow in a Python loop, with no stdlib shortcut -- so it has a hand-written C accelerator
(native/textkernel, raw CPython API) behind this identical-interface Python reference (ADR-0010).

When the C kernel is not built, `levenshtein` runs the pure-Python version below and it still
works; a parity test pins the two equal, and a benchmark records the speedup.

Inputs:  two str (distance) or a word + candidate strings (closest).
Outputs: the edit distance (int), or the nearest candidate (str) / None. Non-str inputs fail loud.
"""

from __future__ import annotations

from collections.abc import Iterable

try:  # pragma: no cover - presence depends on whether the C kernel is built
    import codeforge_textkernel

    _HAS_KERNEL = True
except ImportError:  # pragma: no cover - the pure-Python fallback path
    _HAS_KERNEL = False

# Which implementation `levenshtein` uses right now: the C kernel when built, else pure Python.
TEXTMATCH_BACKEND = "c" if _HAS_KERNEL else "python"


def levenshtein_py(a: str, b: str) -> int:
    """The Levenshtein edit distance (insert/delete/substitute) -- the pure-Python reference.

    A single rolling row of the DP table, kept the size of the shorter string. This is the behaviour
    the C kernel is proven against; keep them in step.
    """
    if not isinstance(a, str) or not isinstance(b, str):
        raise TypeError("levenshtein requires two str")  # noqa: TRY003
    if len(a) > len(b):
        a, b = b, a  # work over columns of the longer string; row stays the shorter length
    if not a:
        return len(b)

    row = list(range(len(a) + 1))
    for j, cb in enumerate(b, start=1):
        diagonal = row[0]
        row[0] = j
        for i, ca in enumerate(a, start=1):
            above = row[i]
            substitute = diagonal + (0 if ca == cb else 1)
            row[i] = min(substitute, row[i] + 1, row[i - 1] + 1)
            diagonal = above
    return row[len(a)]


def levenshtein(a: str, b: str) -> int:
    """Edit distance via the C kernel when built, else the pure-Python reference. Same result."""
    if _HAS_KERNEL:
        return int(codeforge_textkernel.levenshtein(a, b))
    return levenshtein_py(a, b)


def closest(word: str, candidates: Iterable[str], *, max_distance: int | None = None) -> str | None:
    """The candidate nearest `word` by edit distance, or None.

    Ties break to the lexicographically first candidate (deterministic). Returns None when there are
    no candidates, or -- if `max_distance` is given -- when even the nearest is further off (so a
    "did you mean ...?" only fires on a genuine near-miss, never a wild guess).
    """
    best: str | None = None
    best_distance = -1
    for candidate in sorted(set(candidates)):
        distance = levenshtein(word, candidate)
        if best is None or distance < best_distance:
            best, best_distance = candidate, distance
    if best is None:
        return None
    if max_distance is not None and best_distance > max_distance:
        return None
    return best
