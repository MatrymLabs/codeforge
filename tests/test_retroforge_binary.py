"""Test twin for kernel/retroforge/binary.py.

Acceptance: an in-range read returns exactly what was asked for; a window narrows the view.

Refusal (fail loud): a read past the end, a read starting past the end, a negative offset or count,
and a window whose bounds do not fit. Each must RAISE, because the dangerous failure here is not a
crash, it is a short read that decodes into a plausible-looking tile.
"""

from __future__ import annotations

import pytest

from kernel.retroforge.binary import ByteSource, OutOfRange

ROM = ByteSource(bytes(range(16)), name="fixture")


def test_an_in_range_read_returns_exactly_what_was_asked_for() -> None:
    assert ROM.read(0, 4) == bytes([0, 1, 2, 3])
    assert ROM.read(12, 4) == bytes([12, 13, 14, 15])


def test_a_zero_length_read_is_legal_and_empty() -> None:
    assert ROM.read(8, 0) == b""


def test_length_is_the_byte_count() -> None:
    assert len(ROM) == 16


@pytest.mark.parametrize(
    "offset, count",
    [(0, 17), (16, 1), (15, 2), (12, 5)],
    ids=["longer than source", "starts at end", "ends one past", "overruns"],
)
def test_a_read_past_the_end_refuses_rather_than_truncating(offset: int, count: int) -> None:
    """The whole point. A short read renders garbage that looks like data."""
    with pytest.raises(OutOfRange, match="past the 16-byte source"):
        ROM.read(offset, count)


@pytest.mark.parametrize(
    "offset, count", [(-1, 4), (0, -4)], ids=["negative offset", "negative count"]
)
def test_a_negative_read_is_refused(offset: int, count: int) -> None:
    with pytest.raises(OutOfRange, match="negative read"):
        ROM.read(offset, count)


def test_a_window_narrows_the_view_and_renames_it() -> None:
    win = ROM.window(4, 4)
    assert len(win) == 4
    assert win.read(0, 4) == bytes([4, 5, 6, 7])
    assert "fixture[4:8]" in win.name


def test_a_window_past_the_end_is_refused_when_it_is_taken() -> None:
    """Bounds are checked at the window, not deferred to the first read inside it."""
    with pytest.raises(OutOfRange):
        ROM.window(14, 8)


def test_a_window_cannot_read_outside_itself() -> None:
    win = ROM.window(4, 4)
    with pytest.raises(OutOfRange):
        win.read(0, 5)


def test_the_source_exposes_no_way_to_write() -> None:
    """RF-001's safety promise is a property of the type, not a habit of the caller."""
    with pytest.raises((AttributeError, TypeError)):
        ROM.data = b"clobbered"  # type: ignore[misc]
