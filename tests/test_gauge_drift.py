"""Test twin for gauge_drift: acceptance + hostile refusal cases."""

from __future__ import annotations

import pytest

from kernel.shelf.gauge_drift import Gauge, GaugeError

# --- acceptance -----------------------------------------------------------


def test_at_zero_is_current() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=5.0)
    assert g.at(0) == 50.0


def test_positive_rate_rises() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0)
    assert g.at(3) == 80.0


def test_positive_rate_clamps_at_maximum() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0)
    assert g.at(100) == 100.0


def test_negative_rate_falls() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=-10.0)
    assert g.at(2) == 30.0


def test_negative_rate_clamps_at_minimum() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=-10.0)
    assert g.at(100) == 0.0


def test_target_stops_rise_without_overshoot() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0, target=75.0)
    # Un-targeted this would reach 90 in 4 beats; the target caps it at 75.
    assert g.at(4) == 75.0


def test_target_stops_fall_without_overshoot() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=-10.0, target=25.0)
    assert g.at(10) == 25.0


def test_target_not_yet_reached_uses_drift() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0, target=75.0)
    assert g.at(1) == 60.0


def test_advance_is_copy_on_write() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0)
    g2 = g.advance(2)
    assert g.current == 50.0  # original untouched
    assert g2.current == 70.0
    assert g2 is not g


def test_advance_chains_toward_max() -> None:
    g = Gauge(current=0.0, minimum=0.0, maximum=10.0, rate=4.0)
    g2 = g.advance(1).advance(1).advance(1)
    assert g2.current == 10.0  # 4 -> 8 -> clamp 10


# --- refusal (hostile / near-miss) ---------------------------------------


def test_current_above_maximum_fails_loud() -> None:
    with pytest.raises(GaugeError):
        Gauge(current=150.0, minimum=0.0, maximum=100.0, rate=1.0)


def test_current_below_minimum_fails_loud() -> None:
    with pytest.raises(GaugeError):
        Gauge(current=-5.0, minimum=0.0, maximum=100.0, rate=1.0)


def test_minimum_above_maximum_fails_loud() -> None:
    with pytest.raises(GaugeError):
        Gauge(current=5.0, minimum=100.0, maximum=0.0, rate=1.0)


def test_negative_elapsed_fails_loud() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0)
    with pytest.raises(GaugeError):
        g.at(-1)


def test_advance_negative_elapsed_fails_loud() -> None:
    g = Gauge(current=50.0, minimum=0.0, maximum=100.0, rate=10.0)
    with pytest.raises(GaugeError):
        g.advance(-3)
