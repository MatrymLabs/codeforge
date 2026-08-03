"""CARD: gametime -- day/night + named-calendar layer over a monotonic beat counter.

A pure-function calendar for a game clock. The world advances by an integer
"beat" (a monotonic tick). This part converts an absolute beat count into a
human-facing Stamp: year, named month and weekday, day-of-month, hour, and a
day/night phase (dawn / day / dusk / night). It has no state of its own: every
result is a pure function of the beat, so the same beat always renders the same
stamp. It composes with codeforge's climate.py, which derives seasons from the
same beat but has no hours, dawn/dusk, named months, or weekdays.

Clean-room, pattern-not-code, harvested from the shape of Evennia's
utils/gametime.py and contrib custom_gametime (BSD-3-Clause). No source code was
copied; only the idea of a divisor-chain calendar over a tick counter.

BSD-3-Clause attribution (Evennia, https://github.com/evennia/evennia):
  Copyright (c) Evennia contributors. Redistributions of source code must retain
  the above copyright notice, this list of conditions and the following
  disclaimer. Neither the name of Evennia nor the names of its contributors may
  be used to endorse or promote products derived from this software without
  specific prior written permission. THE SOFTWARE IS PROVIDED "AS IS".

Phase thresholds are anchored to a 24 hour day and scaled to hours_per_day:
  dawn starts at 5/24 of the day, day at 7/24, dusk at 18/24, night at 20/24.
For the canonical 24 hour day this gives dawn [5, 7), day [7, 18), dusk [18, 20),
night otherwise. is_daytime is true whenever the sun is up (dawn, day, or dusk).
"""

from __future__ import annotations

from dataclasses import dataclass

# Phase anchors expressed as (hour, hours-in-a-standard-day). Scaled to the
# calendar's hours_per_day so a non-24-hour day still gets sensible twilight.
_STANDARD_DAY_HOURS = 24
_DAWN_START = 5
_DAY_START = 7
_DUSK_START = 18
_NIGHT_START = 20


class GametimeError(ValueError):
    """Raised loud and early on a malformed Calendar or an illegal beat."""


@dataclass(frozen=True)
class Stamp:
    """A resolved calendar reading. Every field is derived from a single beat."""

    year: int
    month: int  # 1-based
    day: int  # 1-based
    hour: int
    weekday_name: str
    month_name: str
    phase: str  # one of "dawn", "day", "dusk", "night"

    def render(self) -> str:
        """Human-facing one-liner, e.g. 'Highsun 14:00, Frostmonth 3, Year 5 (day)'."""
        return (
            f"{self.weekday_name} {self.hour:02d}:00, "
            f"{self.month_name} {self.day}, Year {self.year} ({self.phase})"
        )


@dataclass(frozen=True)
class Calendar:
    """A frozen calendar definition: how beats roll up into hours, days, months, years."""

    beats_per_hour: int
    hours_per_day: int
    days_per_month: int
    month_names: tuple[str, ...]
    weekday_names: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("beats_per_hour", self.beats_per_hour),
            ("hours_per_day", self.hours_per_day),
            ("days_per_month", self.days_per_month),
        ):
            if not isinstance(value, int):
                raise GametimeError(f"{field_name} must be an int, got {value!r}")
            if value <= 0:
                raise GametimeError(f"{field_name} must be positive, got {value}")
        if not self.month_names:
            raise GametimeError("month_names must be non-empty")
        if not self.weekday_names:
            raise GametimeError("weekday_names must be non-empty")
        if any(not name for name in self.month_names):
            raise GametimeError("month_names must not contain empty strings")
        if any(not name for name in self.weekday_names):
            raise GametimeError("weekday_names must not contain empty strings")

    def _phase(self, hour: int) -> str:
        """Map an hour-of-day to a day/night phase, scaled to hours_per_day."""
        span = self.hours_per_day

        def anchor(standard_hour: int) -> int:
            return standard_hour * span // _STANDARD_DAY_HOURS

        dawn, day, dusk, night = (
            anchor(_DAWN_START),
            anchor(_DAY_START),
            anchor(_DUSK_START),
            anchor(_NIGHT_START),
        )
        if dawn <= hour < day:
            return "dawn"
        if day <= hour < dusk:
            return "day"
        if dusk <= hour < night:
            return "dusk"
        return "night"

    def stamp(self, beat: int) -> Stamp:
        """Convert an absolute beat count (>= 0) into a calendar Stamp."""
        if not isinstance(beat, int):
            raise GametimeError(f"beat must be an int, got {beat!r}")
        if beat < 0:
            raise GametimeError(f"beat must be >= 0, got {beat}")

        total_hours = beat // self.beats_per_hour
        hour = total_hours % self.hours_per_day

        total_days = total_hours // self.hours_per_day
        day = total_days % self.days_per_month  # 0-based
        weekday_index = total_days % len(self.weekday_names)

        total_months = total_days // self.days_per_month
        month = total_months % len(self.month_names)  # 0-based
        year = total_months // len(self.month_names)

        return Stamp(
            year=year,
            month=month + 1,
            day=day + 1,
            hour=hour,
            weekday_name=self.weekday_names[weekday_index],
            month_name=self.month_names[month],
            phase=self._phase(hour),
        )

    def is_daytime(self, beat: int) -> bool:
        """True when the sun is up (dawn, day, or dusk); False at night."""
        return self.stamp(beat).phase != "night"
