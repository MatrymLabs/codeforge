"""Test twin for kernel/bench_protocol.py (RD-2026-0002 #16).

The load-bearing rule: a difference inside the noise band is NEUTRAL, not a gain. Acceptance
(Cliff's delta sign/magnitude; the verdict ladder), the honesty (negligible effect -> neutral even
when the median moved; too-few-samples -> inconclusive), the injected-timer measure/interleave, and
refusal.
"""

from __future__ import annotations

import unittest

from kernel import bench_protocol as bp


class CliffsDelta(unittest.TestCase):
    def test_candidate_all_faster_is_delta_one(self):
        self.assertEqual(bp.cliffs_delta([10, 10, 10], [1, 1, 1]), 1.0)

    def test_candidate_all_slower_is_delta_minus_one(self):
        self.assertEqual(bp.cliffs_delta([1, 1, 1], [10, 10, 10]), -1.0)

    def test_identical_is_zero(self):
        self.assertEqual(bp.cliffs_delta([5, 5, 5], [5, 5, 5]), 0.0)

    def test_empty_fails_loud(self):
        with self.assertRaises(bp.BenchProtocolError):
            bp.cliffs_delta([], [1])


class Verdict(unittest.TestCase):
    def test_large_improvement_is_verified(self):
        base = [100, 101, 99, 100, 102, 98]
        cand = [50, 51, 49, 50, 52, 48]
        c = bp.compare_samples(base, cand)
        self.assertEqual(c.label, bp.VERIFIED_IMPROVEMENT)
        self.assertGreater(c.delta, 0)
        self.assertLess(c.median_ratio, 1)

    def test_magnitude_bands(self):
        # exercise each Cliff's-delta band boundary directly
        self.assertEqual(bp._magnitude(0.1), "negligible")
        self.assertEqual(bp._magnitude(0.2), "small")
        self.assertEqual(bp._magnitude(0.4), "medium")
        self.assertEqual(bp._magnitude(0.9), "large")

    def test_a_small_but_real_improvement_is_likely_not_verified(self):
        # candidate faster in most pairs but with overlap -> a real but modest effect
        base = [100, 102, 98, 101, 99, 103, 97, 100, 100, 100]
        cand = [98, 99, 97, 100, 96, 101, 95, 99, 98, 102]
        c = bp.compare_samples(base, cand)
        self.assertIn(c.label, (bp.LIKELY_IMPROVEMENT, bp.VERIFIED_IMPROVEMENT))
        self.assertIn(c.magnitude, ("small", "medium", "large"))
        self.assertGreater(c.delta, 0)

    def test_regression_is_flagged(self):
        base = [50, 51, 49, 50, 52, 48]
        cand = [100, 101, 99, 100, 102, 98]
        self.assertEqual(bp.compare_samples(base, cand).label, bp.REGRESSION)

    def test_a_negligible_effect_is_neutral_even_if_the_median_moved(self):
        # candidate median a hair lower but the distributions overlap heavily -> within noise
        base = [100, 90, 110, 95, 105, 100, 98, 102]
        cand = [99, 91, 109, 96, 104, 101, 97, 103]
        c = bp.compare_samples(base, cand)
        self.assertEqual(c.label, bp.NEUTRAL)
        self.assertEqual(c.magnitude, "negligible")

    def test_too_few_samples_is_inconclusive(self):
        self.assertEqual(bp.compare_samples([1, 2], [1, 2]).label, bp.INCONCLUSIVE)


class Measure(unittest.TestCase):
    def test_measure_discards_warmup_and_uses_injected_timer(self):
        # a scripted clock: each timer() call returns the next value; each measured run consumes two
        ticks = iter(range(0, 1000))
        timer = lambda: next(ticks)  # noqa: E731
        samples = bp.measure(lambda: None, repeats=4, warmup=2, timer=timer)
        self.assertEqual(len(samples), 4)  # warmup runs excluded
        self.assertTrue(all(s == 1 for s in samples))  # each run: start=n, end=n+1 -> 1

    def test_measure_rejects_zero_repeats(self):
        with self.assertRaises(bp.BenchProtocolError):
            bp.measure(lambda: None, repeats=0, timer=lambda: 0.0)

    def test_run_comparison_interleaves_and_verdicts(self):
        # scripted per-run durations via a stateful timer keyed by call parity
        state = {"t": 0.0}

        def timer() -> float:
            return state["t"]

        # baseline runs cost 10, candidate 1; drive the clock inside the fns
        def baseline() -> None:
            state["t"] += 10

        def candidate() -> None:
            state["t"] += 1

        order = ["b", "c"] * 8
        c = bp.run_comparison(baseline, candidate, repeats=8, warmup=1, timer=timer, order=order)
        self.assertEqual(c.label, bp.VERIFIED_IMPROVEMENT)


class Environment(unittest.TestCase):
    def test_describe_environment_reports_a_governor_field(self):
        env = bp.describe_environment()
        self.assertIn("cpu_governor", env)
        self.assertIn("governor_controlled", env)
        self.assertIn("taskset", env["how_to_control"])

    def test_absent_sysfs_reports_unknown_not_a_crash(self):
        env = bp.describe_environment(cpu=999999)  # no such cpu -> sysfs read fails
        self.assertIn("unknown", env["cpu_governor"])

    def test_render_without_environment(self):
        c = bp.compare_samples([1, 2], [1, 2])  # inconclusive; no env passed
        self.assertIn("bench verdict:", bp.render(c))

    def test_render_includes_the_label(self):
        c = bp.compare_samples([100, 101, 99, 100, 102, 98], [50, 51, 49, 50, 52, 48])
        out = bp.render(c, bp.describe_environment())
        self.assertIn("VERIFIED_IMPROVEMENT", out)
        self.assertIn("governor", out)


if __name__ == "__main__":
    unittest.main()
