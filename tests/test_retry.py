"""Test twin for parts/retry.py -- deterministic retry/backoff via an injected sleep."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.retry import Attempt, RetryError, RetryPolicy, run_with_retries


class RecordingSleep:
    """A fake sleep that records the delays it was asked to wait, without waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class Transient(Exception):
    pass


class Permanent(Exception):
    pass


def _flaky(failures: int, exc=Transient):
    """A callable that fails `failures` times, then returns 'ok'. Records its own call count."""
    state = {"calls": 0}

    def fn() -> str:
        state["calls"] += 1
        if state["calls"] <= failures:
            raise exc(f"fail {state['calls']}")
        return "ok"

    fn.calls = state  # type: ignore[attr-defined]
    return fn


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_attempts": 3, "base_delay": -1},
        {"max_attempts": 3, "factor": 0.5},
    ],
)
def test_a_bad_policy_fails_loud(kwargs):
    with pytest.raises(RetryError):
        RetryPolicy(**kwargs)


def test_the_backoff_schedule_is_exponential_and_capped():
    p = RetryPolicy(max_attempts=5, base_delay=1.0, factor=2.0, max_delay=5.0)
    assert [p.delay_for(a) for a in range(1, 5)] == [1.0, 2.0, 4.0, 5.0]  # capped at 5


def test_it_succeeds_without_retrying_when_the_first_try_works():
    sleep = RecordingSleep()
    fn = _flaky(failures=0)
    assert run_with_retries(fn, RetryPolicy(3), sleep=sleep) == "ok"
    assert fn.calls["calls"] == 1
    assert sleep.delays == []  # never slept


def test_a_transient_failure_recovers_and_records_the_backoff():
    sleep = RecordingSleep()
    fn = _flaky(failures=2)
    p = RetryPolicy(max_attempts=5, base_delay=1.0, factor=2.0)
    assert run_with_retries(fn, p, sleep=sleep) == "ok"
    assert fn.calls["calls"] == 3  # failed twice, then succeeded
    assert sleep.delays == [1.0, 2.0]  # two backoffs on the exponential schedule


def test_a_permanent_failure_is_not_retried_and_not_swallowed():
    sleep = RecordingSleep()
    fn = _flaky(failures=1, exc=Permanent)
    p = RetryPolicy(max_attempts=5, retry_on=(Transient,))  # Permanent is not transient
    with pytest.raises(Permanent):
        run_with_retries(fn, p, sleep=sleep)
    assert fn.calls["calls"] == 1  # tried once, gave up immediately
    assert sleep.delays == []


def test_exhausting_attempts_reraises_the_last_failure():
    sleep = RecordingSleep()
    fn = _flaky(failures=99)  # never succeeds
    with pytest.raises(Transient):
        run_with_retries(fn, RetryPolicy(3), sleep=sleep)
    assert fn.calls["calls"] == 3  # exactly max_attempts
    assert len(sleep.delays) == 2  # max_attempts - 1


def test_on_retry_records_an_attempt_history():
    seen: list[Attempt] = []
    fn = _flaky(failures=2)
    run_with_retries(
        fn, RetryPolicy(5, base_delay=1.0), sleep=RecordingSleep(), on_retry=seen.append
    )
    assert [a.number for a in seen] == [1, 2]


@pytest.mark.property
@given(
    max_attempts=st.integers(min_value=1, max_value=20),
    failures=st.integers(min_value=0, max_value=25),
)
def test_fn_is_called_at_most_max_attempts_and_sleeps_are_one_fewer(max_attempts, failures):
    sleep = RecordingSleep()
    fn = _flaky(failures=failures)
    try:
        run_with_retries(fn, RetryPolicy(max_attempts, base_delay=0.0), sleep=sleep)
        succeeded = True
    except Transient:
        succeeded = False
    calls = fn.calls["calls"]
    assert calls <= max_attempts  # the attempt budget is never exceeded
    assert len(sleep.delays) == calls - 1  # one backoff between each pair of tries
    assert succeeded == (failures < max_attempts)
