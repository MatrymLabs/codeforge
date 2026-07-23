"""Test twin for parts/shelf/hourglass.py -- the beat-driven delay queue.

Acceptance: a scheduled payload fires after exactly N beats; repeating timers rearm.
Refusal: a nonsensical schedule (non-positive delay, negative period, overflowing the queue)
fails loud rather than queuing garbage.
"""

import pytest

from parts.shelf.hourglass import MAX_TIMERS, Hourglass, HourglassError


def test_a_timer_fires_after_exactly_n_beats():
    glass = Hourglass()
    glass.schedule("wake", after=3)
    assert glass.advance() == []  # beat 1
    assert glass.advance() == []  # beat 2
    assert glass.advance() == ["wake"]  # beat 3: due, fires its label (no payload given)
    assert glass.advance() == []  # gone -- a one-shot does not fire twice


def test_a_payload_is_returned_when_given_else_the_label():
    glass = Hourglass()
    glass.schedule("relock", after=1, payload=("relock_door", "gate"))
    glass.schedule("bare", after=1)
    fired = glass.advance()
    assert ("relock_door", "gate") in fired and "bare" in fired


def test_a_repeating_timer_rearms_and_fires_every_period():
    glass = Hourglass()
    glass.schedule("beat", after=2, every=2)
    assert glass.advance() == []
    assert glass.advance() == ["beat"]  # fires at 2
    assert glass.advance() == []
    assert glass.advance() == ["beat"]  # and again at 4 -- it rearmed
    assert glass.pending() == 1  # still scheduled


def test_timers_fire_in_insertion_order():
    glass = Hourglass()
    for name in ("first", "second", "third"):
        glass.schedule(name, after=1)
    assert glass.advance() == ["first", "second", "third"]


def test_cancel_removes_a_pending_timer():
    glass = Hourglass()
    glass.schedule("doomed", after=5)
    assert glass.cancel("doomed") is True
    assert glass.cancel("doomed") is False  # already gone
    assert glass.advance() == []


def test_rescheduling_a_label_replaces_it():
    glass = Hourglass()
    glass.schedule("x", after=10)
    glass.schedule("x", after=1)  # same label, new delay -> replaces, not a second timer
    assert glass.pending() == 1
    assert glass.advance() == ["x"]


def test_remaining_and_pending_report_the_queue():
    glass = Hourglass()
    assert glass.remaining("ghost") is None and glass.pending() == 0
    glass.schedule("t", after=4)
    assert glass.remaining("t") == 4
    glass.advance()
    assert glass.remaining("t") == 3 and glass.pending() == 1


@pytest.mark.parametrize("bad", [0, -3, 2.5, True])
def test_a_non_positive_or_non_integer_delay_is_refused(bad):
    with pytest.raises(HourglassError, match="'after'"):
        Hourglass().schedule("x", after=bad)


@pytest.mark.parametrize("bad", [-1, 1.5, True])
def test_a_bad_repeat_period_is_refused(bad):
    with pytest.raises(HourglassError, match="'every'"):
        Hourglass().schedule("x", after=1, every=bad)


def test_clear_empties_the_queue():
    glass = Hourglass()
    glass.schedule("a", after=1)
    glass.schedule("b", after=2)
    glass.clear()
    assert glass.pending() == 0 and glass.advance() == []


def test_the_queue_is_bounded_against_a_denial_of_service():
    glass = Hourglass()
    for i in range(MAX_TIMERS):
        glass.schedule(f"t{i}", after=10)
    assert glass.pending() == MAX_TIMERS
    with pytest.raises(HourglassError, match="full"):
        glass.schedule("one-too-many", after=10)
    # but rescheduling an EXISTING label at the ceiling is fine (no growth)
    glass.schedule("t0", after=1)
    assert glass.pending() == MAX_TIMERS
