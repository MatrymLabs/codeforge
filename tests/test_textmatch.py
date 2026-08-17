"""Test twin for kernel.shelf.textmatch -- edit distance + nearest candidate, C equal to Python.

Acceptance: the reference computes known distances (symmetric, unicode-correct); the active backend
agrees with the reference; and closest() picks the nearest candidate with a deterministic tie-break.
Refusal: non-str inputs fail loud; closest() returns None on no candidates or nothing near enough.

When the C kernel is built, a property test pins it byte-for-byte to the Python reference over
text; when it is not, the reference is the backend and everything still holds.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kernel.shelf.textmatch import TEXTMATCH_BACKEND, closest, levenshtein, levenshtein_py

_HAS_KERNEL = TEXTMATCH_BACKEND == "c"

# hostile on purpose: empty, unicode (café vs cafe), transposition, case, and a long pair.
_PAIRS = [
    ("", "", 0),
    ("a", "", 1),
    ("", "abc", 3),
    ("abc", "abc", 0),
    ("kitten", "sitting", 3),
    ("flaw", "lawn", 2),
    ("look", "lok", 1),
    ("café", "cafe", 1),
    ("Look", "look", 1),  # case matters (edit distance is exact, not folded)
    ("registry", "registri", 1),
]


@pytest.mark.parametrize(("a", "b", "distance"), _PAIRS)
def test_reference_computes_known_distances_symmetrically(a, b, distance):
    assert levenshtein_py(a, b) == distance
    assert levenshtein_py(b, a) == distance  # edit distance is symmetric


@pytest.mark.parametrize(("a", "b", "distance"), _PAIRS)
def test_the_active_backend_matches_the_reference(a, b, distance):
    # levenshtein() is the C kernel when built, else the reference itself; it must agree.
    assert levenshtein(a, b) == distance


def test_non_str_input_fails_loud():
    with pytest.raises(TypeError):
        levenshtein("a", 5)  # not two str
    with pytest.raises(TypeError):
        levenshtein_py(None, "b")  # not two str


@pytest.mark.skipif(not _HAS_KERNEL, reason="C kernel not built (kernel.shelf.textmatch)")
@given(st.text(max_size=40), st.text(max_size=40))
def test_c_kernel_equals_the_python_reference_on_random_text(a, b):
    import codeforge_textkernel  # noqa: PLC0415

    assert codeforge_textkernel.levenshtein(a, b) == levenshtein_py(a, b)


# --- closest(): the "did you mean ...?" primitive ---------------------------------------------


def test_closest_picks_the_nearest_candidate():
    assert closest("lok", ["look", "north", "inventory"]) == "look"
    assert closest("registri", ["registry", "career", "law"]) == "registry"


def test_closest_breaks_ties_lexicographically():
    # "ac" and "ad" are both one edit from "ab"; the first in sorted order wins (deterministic)
    assert closest("ab", ["ad", "ac"]) == "ac"


def test_closest_returns_none_without_candidates():
    assert closest("anything", []) is None


def test_closest_max_distance_blocks_a_wild_guess():
    assert closest("banana", ["look", "north"], max_distance=2) is None  # nothing close enough
    assert closest("lok", ["look"], max_distance=2) == "look"  # a genuine near-miss still fires
