"""Test twin for profile_hotspots.py. It ranks the hottest function first, computes self
percentage, sorts by self vs cumulative, carries the gate caveat, profiles a real callable
end-to-end, and refuses malformed input.

Run:  python3 -m unittest test_profile_hotspots
"""

from __future__ import annotations

import unittest

from parts.shelf.profile_hotspots import CAVEAT, ProfileError, analyze, profile_call, render

# a synthetic pstats mapping: {(file, line, func): (cc, nc, tottime, cumtime, callers)}
STATS: dict[tuple[str, int, str], tuple[int, int, float, float, dict[object, object]]] = {
    ("app.py", 10, "hot"): (1, 1, 0.80, 0.90, {}),  # dominant self time
    ("app.py", 20, "warm"): (5, 5, 0.15, 0.60, {}),
    ("app.py", 30, "cold"): (100, 100, 0.05, 0.05, {}),
    ("driver.py", 1, "main"): (1, 1, 0.00, 1.00, {}),  # all time is in subcalls
}


class Ranking(unittest.TestCase):
    def test_hottest_self_time_ranks_first(self):
        report = analyze(STATS, sort="self")
        self.assertIn("hot", report.prime_hotspot)

    def test_self_percent_computed(self):
        report = analyze(STATS, sort="self")
        hot = report.hotspots[0]
        # total self = 0.80 + 0.15 + 0.05 + 0.00 = 1.00 -> hot is 80%
        self.assertAlmostEqual(hot.self_percent, 80.0, places=1)

    def test_cumulative_sort_puts_main_first(self):
        report = analyze(STATS, sort="cumulative")
        self.assertIn("main", report.prime_hotspot)  # cumtime 1.00 dominates

    def test_top_limit_respected(self):
        self.assertEqual(len(analyze(STATS, top=2).hotspots), 2)

    def test_calls_and_times_carried(self):
        cold = next(h for h in analyze(STATS).hotspots if "cold" in h.function)
        self.assertEqual(cold.calls, 100)
        self.assertEqual(cold.self_time, 0.05)


class Honesty(unittest.TestCase):
    def test_caveat_present_and_names_the_gate(self):
        report = analyze(STATS)
        self.assertEqual(report.caveat, CAVEAT)
        self.assertIn("benchmark", report.caveat)

    def test_zero_time_run_is_noted(self):
        report = analyze({("f.py", 1, "g"): (1, 1, 0.0, 0.0, {})})
        self.assertTrue(any("too fast" in n for n in report.notes))

    def test_render_carries_caveat_and_hotspot(self):
        out = render(analyze(STATS))
        self.assertIn("CAVEAT", out)
        self.assertIn("hot", out)
        self.assertIn("where to look, not what to fix", out)


class Refusal(unittest.TestCase):
    def test_unknown_sort_refused(self):
        with self.assertRaises(ProfileError):
            analyze(STATS, sort="wall_clock")

    def test_non_dict_refused(self):
        with self.assertRaises(ProfileError):
            analyze([("f", 1, "g")])

    def test_malformed_row_refused(self):
        with self.assertRaises(ProfileError):
            analyze({("f.py", 1, "g"): (1, 2)})


class RealProfile(unittest.TestCase):
    def test_profile_call_finds_the_busy_function(self):
        def busy() -> int:
            total = 0
            for i in range(200_000):
                total += i * i
            return total

        def driver() -> None:
            busy()

        report = profile_call(driver)
        # busy() should appear among the hotspots with real recorded time
        self.assertTrue(any("busy" in h.function for h in report.hotspots))
        self.assertGreater(report.total_self_time, 0.0)


if __name__ == "__main__":
    unittest.main()
