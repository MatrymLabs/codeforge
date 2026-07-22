"""CARD: calibrate -- the game adapter for retry: auto-retry a flaky calibration.

A player `calibrate`s a temperamental instrument that fails transiently more often than not; the
retry core (`parts/retry`) tries again automatically and reports which attempt finally took, or that
it gave up. The SAME `run_with_retries` core retries an unreliable API/DB call in a practical app
(`parts/resilient_call`); only the adapter differs. The tick is synchronous, so the in-game policy
uses a zero delay (a real backoff would block every player); the delay behavior is proven in the
core and practical tests.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from parts.session import Session
from parts.shelf.retry import RetryPolicy, run_with_retries

_POLICY = RetryPolicy(max_attempts=4, base_delay=0.0)  # zero delay: never block the tick
_rng_override: Callable[[], float] | None = None


class _CalibrationFault(Exception):
    """The instrument slipped this attempt (a transient failure the retry core will retry)."""


def _calibrate_once(rng: Callable[[], float]) -> str:
    if rng() < 0.6:  # transient failure most of the time
        raise _CalibrationFault("the coil slipped")
    return "aligned"


def calibrate(session: Session, arg: str = "") -> str:
    """The `calibrate` verb: retry a flaky instrument calibration and report the outcome."""
    rng = _rng_override or random.random
    tally = {"n": 0}

    def once() -> str:
        tally["n"] += 1
        return _calibrate_once(rng)

    try:
        result = run_with_retries(once, _POLICY, sleep=_no_sleep)
        return f"You calibrate the instrument. {result.capitalize()} on attempt {tally['n']}."
    except _CalibrationFault:
        return f"The instrument resists you. Calibration failed after {tally['n']} attempts."


def _no_sleep(_delay: float) -> None:
    """The tick is synchronous; never actually sleep inside a command."""


def set_calibration_rng(rng: Callable[[], float] | None = None) -> None:
    """Test hook: inject a deterministic 0..1 source (or None to restore real randomness)."""
    global _rng_override
    _rng_override = rng
