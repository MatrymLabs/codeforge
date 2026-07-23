"""Test twin for parts/login_guard.py -- the practical adapter + the one-core-two-adapters proof."""

from parts.login_guard import LoginGuard
from parts.shelf.token_bucket import TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_five_attempts_are_allowed_then_the_sixth_is_denied():
    guard = LoginGuard(clock=FakeClock())
    for _ in range(5):
        assert guard.attempt("alice").allowed
    denied = guard.attempt("alice")
    assert not denied.allowed
    assert denied.retry_after > 0


def test_attempts_refill_over_time():
    clk = FakeClock()
    guard = LoginGuard(clock=clk)
    for _ in range(5):
        guard.attempt("bob")
    assert not guard.attempt("bob").allowed
    clk.advance(30)  # one attempt refills every 30s
    assert guard.attempt("bob").allowed


def test_keys_are_isolated():
    guard = LoginGuard(clock=FakeClock())
    for _ in range(5):
        guard.attempt("carol")
    assert not guard.attempt("carol").allowed
    assert guard.attempt("dave").allowed  # a different account still has its full burst


def test_one_core_powers_both_the_game_shout_and_the_practical_login_guard():
    # The whole point of the slice: the SAME TokenBucket core drives both adapters.
    from parts import chat_throttle

    guard = LoginGuard(clock=FakeClock())
    guard.attempt("eve")
    assert any(isinstance(b, TokenBucket) for b in guard._buckets.values())
    # and the game adapter builds the same core type
    chat_throttle.reset_throttles()
    chat_throttle.shout(_stub_session(), "hi")
    assert all(isinstance(b, TokenBucket) for b in chat_throttle._BUCKETS.values())


def _stub_session():
    from parts.world.session import SESSIONS, Session

    s = Session(player_id="shouter", location="courtyard")
    SESSIONS["shouter"] = s
    return s


def test_the_bucket_map_is_bounded_against_a_flood_of_keys(monkeypatch):
    # A flood of distinct keys (IPs/accounts) must not grow the bucket map without bound.
    from parts import login_guard

    monkeypatch.setattr(login_guard, "_MAX_KEYS", 3)
    guard = login_guard.LoginGuard()
    for i in range(20):
        guard.attempt(f"key-{i}")
    assert len(guard._buckets) <= 3
