"""CARD: test_line_editor -- acceptance + refusal cases for the Buffer part.

Clean-room test twin (BSD-3-Clause lineage, Evennia utils/eveditor.py concept).
"""

from __future__ import annotations

import pytest

from kernel.shelf.line_editor import Buffer, EditorError


def test_empty_buffer_len_zero() -> None:
    assert len(Buffer()) == 0


def test_append_grows() -> None:
    buf = Buffer().append("first").append("second")
    assert buf.lines == ("first", "second")
    assert len(buf) == 2


def test_insert_shifts_existing_lines() -> None:
    buf = Buffer(("a", "c")).insert(2, "b")
    assert buf.lines == ("a", "b", "c")


def test_insert_at_end_appends() -> None:
    buf = Buffer(("a", "b")).insert(3, "c")
    assert buf.lines == ("a", "b", "c")


def test_insert_into_empty() -> None:
    assert Buffer().insert(1, "only").lines == ("only",)


def test_delete_removes_line() -> None:
    buf = Buffer(("a", "b", "c")).delete(2)
    assert buf.lines == ("a", "c")


def test_replace_substitutes_across_lines() -> None:
    buf = Buffer(("foo bar", "bar foo")).replace("foo", "XXX")
    assert buf.lines == ("XXX bar", "bar XXX")


def test_clear_empties_buffer() -> None:
    assert Buffer(("a", "b")).clear().lines == ()


def test_text_joins_with_newlines() -> None:
    assert Buffer(("one", "two")).text() == "one\ntwo"


def test_render_numbers_lines() -> None:
    assert Buffer(("hi", "yo")).render() == "1: hi\n2: yo"


def test_copy_on_write_leaves_original_unchanged() -> None:
    original = Buffer(("a", "b"))
    original.append("c")
    original.insert(1, "z")
    original.delete(1)
    original.replace("a", "Q")
    original.clear()
    assert original.lines == ("a", "b")


def test_buffer_is_frozen() -> None:
    buf = Buffer(("a",))
    with pytest.raises(Exception):  # noqa: B017 -- FrozenInstanceError is a dataclasses detail
        buf.lines = ("b",)  # type: ignore[misc]


def test_insert_out_of_range_fails_loud() -> None:
    with pytest.raises(EditorError):
        Buffer(("a",)).insert(5, "x")


def test_delete_out_of_range_fails_loud() -> None:
    with pytest.raises(EditorError):
        Buffer(("a", "b")).delete(9)


def test_delete_on_empty_fails_loud() -> None:
    with pytest.raises(EditorError):
        Buffer().delete(1)


def test_editor_error_is_value_error() -> None:
    assert issubclass(EditorError, ValueError)
