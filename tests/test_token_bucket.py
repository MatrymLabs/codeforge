"""Test twin for parts/token_bucket.py -- deterministic rate limiting via an injected clock."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.token_bucket import RateLimitError, TokenBucket


class FakeClock:
    """A controllable monotonic clock so tests pin exact refill behavior without sleeping."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_a_fresh_bucket_starts_full_and_allows_a_burst():
    b = TokenBucket(rate=1.0, capacity=3.0, clock=FakeClock())
    assert b.consume().allowed  # 3 -> 2
    assert b.consume().allowed  # 2 -> 1
    assert b.consume().allowed  # 1 -> 0
    denied = b.consume()  # 0 -> denied
    assert not denied.allowed
    assert denied.retry_after == pytest.approx(1.0)  # 1 token needed / 1 per sec
    assert "rate limit" in denied.reason


def test_it_refills_over_time_via_the_injected_clock():
    clk = FakeClock()
    b = TokenBucket(rate=2.0, capacity=2.0, clock=clk)
    b.consume()
    b.consume()
    assert not b.consume().allowed  # empty
    clk.advance(0.5)  # 0.5s * 2/s = exactly one token
    assert b.consume().allowed
    assert not b.consume().allowed


def test_refill_never_exceeds_capacity():
    clk = FakeClock()
    b = TokenBucket(rate=100.0, capacity=2.0, clock=clk)
    clk.advance(1000)  # would add 100000 tokens; capped at capacity
    assert b.check().tokens_left == 2.0


def test_check_peeks_without_consuming():
    b = TokenBucket(1.0, 1.0, clock=FakeClock())
    assert b.check().allowed
    assert b.check().allowed  # still allowed: check never consumed
    assert b.consume().allowed
    assert not b.check().allowed


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_a_bad_rate_or_capacity_fails_loud(bad):
    with pytest.raises(RateLimitError):
        TokenBucket(rate=bad, capacity=1.0, clock=FakeClock())
    with pytest.raises(RateLimitError):
        TokenBucket(rate=1.0, capacity=bad, clock=FakeClock())


def test_an_impossible_or_bad_cost_is_refused_loud():
    b = TokenBucket(1.0, 3.0, clock=FakeClock())
    with pytest.raises(RateLimitError):
        b.consume(cost=4.0)  # larger than capacity: could never fit
    with pytest.raises(RateLimitError):
        b.consume(cost=float("nan"))
    with pytest.raises(RateLimitError):
        b.consume(cost=-1.0)


@pytest.mark.property
@given(
    rate=st.floats(min_value=0.1, max_value=100, allow_nan=False, allow_infinity=False),
    capacity=st.floats(min_value=1.0, max_value=100, allow_nan=False, allow_infinity=False),
    steps=st.lists(
        st.floats(min_value=0.0, max_value=100, allow_nan=False, allow_infinity=False),
        max_size=60,
    ),
)
def test_never_exceeds_the_configured_rate(rate, capacity, steps):
    # The token-bucket conservation law: starting full, over ANY timeline the total consumed
    # can never exceed the initial capacity plus what the rate could have refilled.
    clk = FakeClock()
    b = TokenBucket(rate, capacity, clock=clk)
    consumed = 0.0
    for dt in steps:
        clk.advance(dt)
        if b.consume(cost=1.0).allowed:
            consumed += 1.0
    assert consumed <= capacity + rate * clk.t + 1e-6
