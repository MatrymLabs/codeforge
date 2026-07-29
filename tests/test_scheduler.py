"""Test twin for parts/world/scheduler.py -- the beat-driven timed-job registry.

Acceptance: a one-shot fires exactly once when its due beat arrives (not before) and is then gone; a
recurring job fires every interval and re-arms. Refusal: a job that raises is dropped rather than
crashing run_due or wedging the clock. Deterministic: driven by a beat number, no wall-clock.
"""

from __future__ import annotations

import pytest

from parts.world import scheduler


@pytest.fixture(autouse=True)
def _clean():
    scheduler.clear()
    yield
    scheduler.clear()


# --- acceptance -------------------------------------------------------------------------------
def test_a_one_shot_fires_once_at_its_due_beat():
    fired: list[int] = []
    scheduler.schedule(5, lambda: fired.append(1))
    assert scheduler.run_due(4) == 0 and fired == []  # not yet due
    assert scheduler.run_due(5) == 1 and fired == [1]  # due now
    assert scheduler.run_due(6) == 0 and fired == [1]  # gone, never fires again
    assert scheduler.pending() == 0


def test_an_overdue_job_still_fires():
    fired: list[int] = []
    scheduler.schedule(3, lambda: fired.append(1))
    assert scheduler.run_due(10) == 1 and fired == [1]  # due beat passed while idle: still fires


def test_a_recurring_job_re_arms_each_interval():
    ticks: list[int] = []
    scheduler.schedule(2, lambda: ticks.append(1), every=3)
    scheduler.run_due(2)  # fires at 2, re-arms for 5
    assert scheduler.pending() == 1
    scheduler.run_due(4)  # not yet due again
    scheduler.run_due(5)  # fires, re-arms for 8
    assert ticks == [1, 1] and scheduler.pending() == 1


# --- refusal / safety --------------------------------------------------------------------------
def test_a_job_that_raises_is_dropped_not_propagated():
    def _boom() -> None:
        raise RuntimeError("scheduled task blew up")

    good: list[int] = []
    scheduler.schedule(1, _boom)
    scheduler.schedule(1, lambda: good.append(1))
    fired = scheduler.run_due(1)  # must not raise
    assert good == [1]  # the healthy job still ran
    assert fired == 1  # only the good one counts as fired
    assert scheduler.pending() == 0  # the broken job was dropped


def test_clear_empties_the_registry():
    scheduler.schedule(1, lambda: None)
    scheduler.schedule(9, lambda: None, every=2)
    assert scheduler.pending() == 2
    scheduler.clear()
    assert scheduler.pending() == 0
