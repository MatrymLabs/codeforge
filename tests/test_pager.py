"""CARD: test_pager -- acceptance + refusal cases for the pager part.

Clean-room test twin (BSD-3-Clause lineage, Evennia utils/evmore.py concept).
"""

from __future__ import annotations

import pytest

from kernel.shelf.pager import PagerError, page_count, paginate


def test_short_text_is_one_page() -> None:
    assert paginate("a\nb\nc", height=10) == ["a\nb\nc"]


def test_splits_at_height() -> None:
    text = "\n".join(str(n) for n in range(6))
    pages = paginate(text, height=2)
    assert pages == ["0\n1", "2\n3", "4\n5"]


def test_exact_multiple_of_height() -> None:
    text = "\n".join(str(n) for n in range(4))
    assert paginate(text, height=2) == ["0\n1", "2\n3"]


def test_wrapping_increases_pages() -> None:
    text = "wordone wordtwo wordthree wordfour"
    without = page_count(text, height=1)
    with_wrap = page_count(text, height=1, width=8)
    assert with_wrap > without


def test_page_count_matches_paginate() -> None:
    text = "\n".join(str(n) for n in range(7))
    assert page_count(text, height=3) == len(paginate(text, height=3))


def test_wrap_preserves_blank_lines() -> None:
    text = "alpha\n\nbeta"
    pages = paginate(text, height=10, width=20)
    assert pages == ["alpha\n\nbeta"]


def test_wrap_produces_more_rows() -> None:
    # One long source line wraps into several display rows across pages.
    text = "aaaa bbbb cccc dddd"
    pages = paginate(text, height=1, width=4)
    assert pages == ["aaaa", "bbbb", "cccc", "dddd"]


def test_empty_text_is_one_empty_page() -> None:
    assert paginate("", height=5) == [""]


def test_height_zero_fails_loud() -> None:
    with pytest.raises(PagerError):
        paginate("anything", height=0)


def test_negative_height_fails_loud() -> None:
    with pytest.raises(PagerError):
        page_count("anything", height=-3)


def test_width_zero_fails_loud() -> None:
    with pytest.raises(PagerError):
        paginate("anything", height=5, width=0)


def test_pager_error_is_value_error() -> None:
    assert issubclass(PagerError, ValueError)
