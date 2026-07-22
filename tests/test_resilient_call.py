"""Test twin for parts/resilient_call.py -- the practical adapter + the one-core proof."""

import pytest

from parts.resilient_call import ResilientCaller
from parts.shelf.retry import RetryPolicy


class NoSleep:
    def __call__(self, delay: float) -> None:
        pass


class Flaky(Exception):
    pass


def _fails_then_ok(failures: int):
    state = {"calls": 0}

    def fn() -> str:
        state["calls"] += 1
        if state["calls"] <= failures:
            raise Flaky(f"fail {state['calls']}")
        return "ok"

    return fn


def test_it_recovers_from_transient_failures_and_records_the_history():
    caller = ResilientCaller(RetryPolicy(5, base_delay=1.0), sleep=NoSleep())
    assert caller.call(_fails_then_ok(2)) == "ok"
    assert [a.number for a in caller.history] == [1, 2]  # two retried attempts recorded
    assert caller.history[0].delay == 1.0


def test_a_permanent_failure_propagates():
    caller = ResilientCaller(RetryPolicy(3, retry_on=(ValueError,)), sleep=NoSleep())
    with pytest.raises(Flaky):  # Flaky is not in retry_on
        caller.call(_fails_then_ok(1))


def test_the_history_resets_between_calls():
    caller = ResilientCaller(RetryPolicy(5), sleep=NoSleep())
    caller.call(_fails_then_ok(2))
    caller.call(_fails_then_ok(0))  # succeeds first try
    assert caller.history == []  # cleared, no leftover attempts


def test_one_core_powers_both_the_game_calibrate_and_the_practical_caller():
    # The whole point of the slice: both adapters run through the same run_with_retries core.
    import parts.calibrate as game
    import parts.resilient_call as practical
    from parts.shelf.retry import run_with_retries

    assert game.run_with_retries is run_with_retries
    assert practical.run_with_retries is run_with_retries
