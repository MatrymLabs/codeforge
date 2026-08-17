"""Test twin for kernel/world/climate.py -- the world's season and weather on the beat.

Acceptance: season wheels through the year and weather shifts within a season, both derived PURELY
from the beat (same beat, same sky). The `weather` view and the tick compose; the tick is silent.
"""

from __future__ import annotations

from kernel.world import climate
from kernel.world.climate import SEASONS, climate_line, season_of, weather_of


def test_season_wheels_through_the_year():
    # each season holds for a block of beats, then turns; a full year returns to spring
    assert season_of(0) == "spring"
    seen = [season_of(b) for b in range(0, 160, 40)]
    assert seen == list(SEASONS), "the year turns spring -> summer -> autumn -> winter"
    assert season_of(160) == "spring", "and wheels back round"


def test_weather_belongs_to_its_season_and_holds_then_shifts():
    from kernel.world.climate import _WEATHER

    for beat in (0, 7, 45, 120):
        assert weather_of(beat) in _WEATHER[season_of(beat)], "weather fits its season"
    # weather holds for a block of beats, then shifts
    assert weather_of(0) == weather_of(6), "the sky holds within a weather block"
    assert weather_of(0) != weather_of(7), "then it shifts"


def test_the_sky_is_pure_and_deterministic():
    assert all(weather_of(b) == weather_of(b) for b in range(200))
    assert climate_line(45).startswith("It is summer.")


def test_climate_line_reads_cleanly():
    line = climate_line(85)  # autumn (85 // 40 = 2)
    assert line.startswith("It is autumn.") and line.endswith(".")


def test_the_tick_advances_the_beat_silently_and_weather_view_reads_it():
    start = climate.now()
    assert climate.tick_climate(object()) == "", "the tick is silent"
    assert climate.now() == start + 1, "and advances the world beat"
    assert "It is" in climate.weather_view(object())
