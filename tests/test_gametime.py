"""CARD: test_gametime -- twin for gametime.py (acceptance + hostile/refusal cases)."""

from __future__ import annotations

import unittest

from kernel.shelf.gametime import Calendar, GametimeError, Stamp

MONTHS = (
    "Frostmonth",
    "Thawmonth",
    "Seedmonth",
    "Bloommonth",
    "Sunmonth",
    "Highmonth",
    "Harvestmonth",
    "Embermonth",
    "Fademonth",
    "Duskmonth",
    "Longnight",
    "Yearsend",
)
WEEKDAYS = (
    "Firstday",
    "Forgeday",
    "Midweek",
    "Emberday",
    "Highsun",
    "Restday",
    "Spiralday",
)


def make_calendar() -> Calendar:
    """A canonical 24 hour day: 1 beat/hour, 30 days/month, 12 months, 7 weekdays."""
    return Calendar(
        beats_per_hour=1,
        hours_per_day=24,
        days_per_month=30,
        month_names=MONTHS,
        weekday_names=WEEKDAYS,
    )


class AcceptanceTests(unittest.TestCase):
    def test_beat_zero_is_origin(self) -> None:
        stamp = make_calendar().stamp(0)
        self.assertEqual(stamp.year, 0)
        self.assertEqual(stamp.month, 1)
        self.assertEqual(stamp.day, 1)
        self.assertEqual(stamp.hour, 0)

    def test_hour_rolls_over_to_next_day(self) -> None:
        cal = make_calendar()
        end_of_day_one = cal.stamp(23)
        self.assertEqual((end_of_day_one.day, end_of_day_one.hour), (1, 23))
        next_day = cal.stamp(24)
        self.assertEqual((next_day.day, next_day.hour), (2, 0))

    def test_day_rolls_over_to_next_month(self) -> None:
        cal = make_calendar()
        beat = 30 * 24  # first beat of day 31 -> month 2, day 1
        stamp = cal.stamp(beat)
        self.assertEqual((stamp.month, stamp.day), (2, 1))
        self.assertEqual(stamp.month_name, "Thawmonth")

    def test_month_rolls_over_to_next_year(self) -> None:
        cal = make_calendar()
        beat = 12 * 30 * 24  # first beat past a full year of months
        stamp = cal.stamp(beat)
        self.assertEqual((stamp.year, stamp.month, stamp.day), (1, 1, 1))

    def test_weekday_cycles(self) -> None:
        cal = make_calendar()
        first = cal.stamp(0)
        one_week_later = cal.stamp(7 * 24)
        self.assertEqual(first.weekday_name, WEEKDAYS[0])
        self.assertEqual(one_week_later.weekday_name, WEEKDAYS[0])
        # And the day in between advanced the weekday.
        self.assertEqual(cal.stamp(24).weekday_name, WEEKDAYS[1])

    def test_beats_per_hour_greater_than_one(self) -> None:
        cal = Calendar(
            beats_per_hour=10,
            hours_per_day=24,
            days_per_month=30,
            month_names=MONTHS,
            weekday_names=WEEKDAYS,
        )
        # 10 beats to advance one hour; 9 beats is still hour 0.
        self.assertEqual(cal.stamp(9).hour, 0)
        self.assertEqual(cal.stamp(10).hour, 1)

    def test_phase_dawn(self) -> None:
        self.assertEqual(make_calendar().stamp(6).phase, "dawn")

    def test_phase_day(self) -> None:
        self.assertEqual(make_calendar().stamp(12).phase, "day")

    def test_phase_dusk(self) -> None:
        self.assertEqual(make_calendar().stamp(19).phase, "dusk")

    def test_phase_night(self) -> None:
        self.assertEqual(make_calendar().stamp(2).phase, "night")
        self.assertEqual(make_calendar().stamp(23).phase, "night")

    def test_is_daytime_true_when_sun_up(self) -> None:
        cal = make_calendar()
        self.assertTrue(cal.is_daytime(12))  # day
        self.assertTrue(cal.is_daytime(6))  # dawn
        self.assertTrue(cal.is_daytime(19))  # dusk

    def test_is_daytime_false_at_night(self) -> None:
        cal = make_calendar()
        self.assertFalse(cal.is_daytime(2))
        self.assertFalse(cal.is_daytime(23))

    def test_render_reads_naturally(self) -> None:
        cal = make_calendar()
        # Highsun (weekday 4) at hour 14, Frostmonth day 3, Year 5.
        # Year 5 -> 5 * 12 * 30 * 24 hours; Frostmonth day 3 -> 2 days; hour 14.
        beat = (5 * 12 * 30 * 24) + (2 * 24) + 14
        stamp = cal.stamp(beat)
        self.assertEqual(stamp.render(), "Emberday 14:00, Frostmonth 3, Year 5 (day)")

    def test_stamp_is_pure_function_of_beat(self) -> None:
        cal = make_calendar()
        self.assertEqual(cal.stamp(12345), cal.stamp(12345))
        self.assertIsInstance(cal.stamp(0), Stamp)


class HostileTests(unittest.TestCase):
    def test_negative_beat_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            make_calendar().stamp(-1)

    def test_zero_beats_per_hour_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            Calendar(
                beats_per_hour=0,
                hours_per_day=24,
                days_per_month=30,
                month_names=MONTHS,
                weekday_names=WEEKDAYS,
            )

    def test_zero_hours_per_day_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            Calendar(
                beats_per_hour=1,
                hours_per_day=0,
                days_per_month=30,
                month_names=MONTHS,
                weekday_names=WEEKDAYS,
            )

    def test_negative_days_per_month_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            Calendar(
                beats_per_hour=1,
                hours_per_day=24,
                days_per_month=-5,
                month_names=MONTHS,
                weekday_names=WEEKDAYS,
            )

    def test_empty_month_names_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            Calendar(
                beats_per_hour=1,
                hours_per_day=24,
                days_per_month=30,
                month_names=(),
                weekday_names=WEEKDAYS,
            )

    def test_empty_weekday_names_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            Calendar(
                beats_per_hour=1,
                hours_per_day=24,
                days_per_month=30,
                month_names=MONTHS,
                weekday_names=(),
            )

    def test_blank_month_name_fails_loud(self) -> None:
        with self.assertRaises(GametimeError):
            Calendar(
                beats_per_hour=1,
                hours_per_day=24,
                days_per_month=30,
                month_names=("Frostmonth", ""),
                weekday_names=WEEKDAYS,
            )


if __name__ == "__main__":
    unittest.main()
