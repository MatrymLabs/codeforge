"""CARD: climate -- the world's SEASON and WEATHER, turning on the beat (the world-sim clock).

A living world has a sky. This is the first slice of the world-simulation layer the campaign (Part
IV) asks for: a season that wheels through the year and weather that shifts with it, both derived
PURELY from the world's beat so any two readers agree and a test can name the day. It is atmosphere
now (the `weather` verb), and the seam later -- 'seasonal availability' and 'weather-dependent
spawns' read `season_of` / `weather_of` to gate what appears.

The beat is the player's command (the one clock; parts.forge advances it after each tick, beside the
zone reset and the menace clock -- no background thread). The counter is runtime, like the zone
beats: a fresh boot starts the year at its first day. The MATH is pure and total, so seasonal and
weather logic is tested without booting a world.
"""

from __future__ import annotations

SEASONS: tuple[str, ...] = ("spring", "summer", "autumn", "winter")
_SEASON_LENGTH = 40  # beats per season; a full turning of the year is 4 x 40 = 160 beats
_WEATHER_LENGTH = 7  # beats one weather state holds before the sky shifts

# The weather a season can wear -- a small, evocative pool each, chosen by the beat within it.
_WEATHER: dict[str, tuple[str, ...]] = {
    "spring": (
        "a mild breeze blows",
        "a soft rain falls",
        "the sun breaks warm",
        "low mist clings",
    ),
    "summer": (
        "the sun beats down",
        "the air hangs hot and still",
        "a dry wind lifts dust",
        "thunderheads gather",
    ),
    "autumn": (
        "a cold rain falls",
        "leaves skirl on the wind",
        "a grey overcast holds",
        "the first frost bites",
    ),
    "winter": (
        "snow drifts down",
        "a bitter wind howls",
        "the cold is iron-hard",
        "ice sheathes the world",
    ),
}


def season_of(beat: int) -> str:
    """The season at a given world beat -- spring, summer, autumn, winter, wheeling on the year."""
    return SEASONS[(beat // _SEASON_LENGTH) % len(SEASONS)]


def weather_of(beat: int) -> str:
    """The weather at a given world beat: one of its season's states, holding for `_WEATHER_LENGTH`
    beats before the sky shifts. Pure -- the same beat always wears the same sky."""
    pool = _WEATHER[season_of(beat)]
    return pool[(beat // _WEATHER_LENGTH) % len(pool)]


def climate_line(beat: int) -> str:
    """A readable line for a beat's sky: 'It is autumn. A cold rain falls.'"""
    weather = weather_of(beat)
    return f"It is {season_of(beat)}. {weather[0].upper()}{weather[1:]}."


# --- the runtime clock (a single world beat counter, advanced on the tick) ---------------------
_beat = 0


def now() -> int:
    """The current world beat (runtime; a fresh boot starts at 0)."""
    return _beat


def advance() -> None:
    """Take one world beat. Called on the tick beside the zone and menace clocks."""
    global _beat
    _beat += 1


def tick_climate(session: object) -> str:
    """Advance the climate one beat on the world's tick. Silent (the sky is read with `weather`, not
    announced every step), so it returns '' and composes into the beat like the other tickers."""
    advance()
    return ""


def weather_view(session: object) -> str:
    """`weather` -- the season and sky over the world right now."""
    return climate_line(_beat)
