"""Test twin for parts/ai_throttle.py -- the game adapter: a rate-limited Architect consultation.

Network-free: with no CODEFORGE_ARCHITECT/ANTHROPIC_API_KEY in the env (as in CI), consult()
resolves the local rule-based guide, so these tests never touch an API. We assert the GATE, not
the guide's wording.
"""

import pytest

from forge import handle_command
from parts.ai_throttle import _CAPACITY, ask_architect, reset_ai_throttle
from parts.session import SESSIONS, Session

_THROTTLED = "The Architect is still thinking"


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@pytest.fixture(autouse=True)
def fresh():
    reset_ai_throttle()
    SESSIONS.clear()
    yield
    reset_ai_throttle()
    SESSIONS.clear()


def _player(pid: str = "matrym") -> Session:
    s = Session(player_id=pid, location="courtyard")
    SESSIONS[pid] = s
    return s


def test_a_consultation_passes_the_gate():
    """An in-budget ask reaches the Architect (the local guide), not the throttle refusal."""
    out = ask_architect(_player(), "how do I forge a part")
    assert _THROTTLED not in out
    assert out.strip()  # the guide said something


def test_over_asking_is_throttled_with_the_wait():
    clk = FakeClock()
    reset_ai_throttle(clock=clk)
    s = _player()
    for _ in range(int(_CAPACITY)):  # burst of three passes
        assert _THROTTLED not in ask_architect(s, "advise me")
    refused = ask_architect(s, "advise me")  # the fourth is capped
    assert _THROTTLED in refused
    assert "s." in refused  # carries the exact wait


def test_the_bucket_refills_over_time():
    clk = FakeClock()
    reset_ai_throttle(clock=clk)
    s = _player()
    for _ in range(int(_CAPACITY)):
        ask_architect(s, "advise me")
    assert _THROTTLED in ask_architect(s, "advise me")  # drained
    clk.advance(30)  # one token back after 30s
    assert _THROTTLED not in ask_architect(s, "advise me")


def test_each_player_gets_their_own_budget():
    clk = FakeClock()
    reset_ai_throttle(clock=clk)
    a, b = _player("aria"), _player("borin")
    for _ in range(int(_CAPACITY)):
        ask_architect(a, "advise me")
    assert _THROTTLED in ask_architect(a, "advise me")  # a is drained
    assert _THROTTLED not in ask_architect(b, "advise me")  # b is untouched


def test_ai_verb_reaches_the_gate_through_the_tick():
    """The feature isn't wired until handle_command proves it: dispatch `ai` on the spine and
    confirm both the pass-through and the cap fire through the real engine door."""
    clk = FakeClock()
    reset_ai_throttle(clock=clk)
    s = _player()
    assert _THROTTLED not in handle_command(s, "ai how do I begin")
    for _ in range(int(_CAPACITY)):
        handle_command(s, "ai keep asking")
    assert _THROTTLED in handle_command(s, "ai one too many")
