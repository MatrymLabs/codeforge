"""CARD: gauge_drift -- a bounded gauge that drifts toward a target over elapsed beats.

Clean-room harvest of the rate-drift idea from Evennia's contrib
rpg/traits CounterTrait rate logic (BSD-3-Clause). No Evennia source was
copied; only the "a bounded value changes by a rate per elapsed time and
stops at a target/bound" behavior is reproduced here in stdlib-only frameless
Python.

Why this exists: codeforge's resources.py is a clamped gauge but has no
continuous rate drift. This adds it, so stamina / thirst / fatigue can bleed
toward a floor, ceiling, or a chosen target across game beats.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

__all__ = ["Gauge", "GaugeError"]


class GaugeError(ValueError):
    """Raised loud when a gauge is built out of bounds or advanced by negative time."""


@dataclass(frozen=True)
class Gauge:
    """A clamped value that drifts by `rate` units per beat toward a target or bound.

    Fields:
      current: the value now (must sit within [minimum, maximum]).
      minimum, maximum: hard bounds (minimum <= maximum).
      rate: units per beat; may be negative to drift down.
      target: an optional soft stop the drift will not overshoot; None means
              drift runs all the way to whichever bound the rate points at.
    """

    current: float
    minimum: float
    maximum: float
    rate: float
    target: float | None = None

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise GaugeError(f"minimum {self.minimum} must be <= maximum {self.maximum}")
        if not (self.minimum <= self.current <= self.maximum):
            raise GaugeError(
                f"current {self.current} must sit within [{self.minimum}, {self.maximum}]"
            )

    def at(self, elapsed_beats: int) -> float:
        """Value after `elapsed_beats`, clamped to bounds and not past `target`.

        Refuses (GaugeError): elapsed_beats < 0.
        """
        if elapsed_beats < 0:
            raise GaugeError(f"elapsed_beats must be >= 0, got {elapsed_beats}")

        drifted = self.current + self.rate * elapsed_beats
        bounded = _clamp(drifted, self.minimum, self.maximum)

        if self.target is None:
            return bounded
        return _clamp_toward_target(self.current, bounded, self.target)

    def advance(self, elapsed_beats: int) -> Gauge:
        """Return a NEW Gauge (copy-on-write) with current = at(elapsed_beats)."""
        return replace(self, current=self.at(elapsed_beats))


def _clamp(value: float, low: float, high: float) -> float:
    """Pin value into [low, high]."""
    return max(low, min(high, value))


def _clamp_toward_target(start: float, drifted: float, target: float) -> float:
    """Stop `drifted` at `target` when it would overshoot past it from `start`."""
    if drifted >= start:
        # Rising (or flat): the target is a ceiling we must not pass.
        return min(drifted, target) if target >= start else start
    # Falling: the target is a floor we must not pass.
    return max(drifted, target) if target <= start else start
