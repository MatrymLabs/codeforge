"""Test twin for sbfl.py. It ranks the truly-faulty line to the top on a classic spectrum,
implements each formula, keeps the honesty caveat, handles the no-failure and
covered-only-by-passing cases, and refuses malformed input.

Run:  python3 -m unittest test_sbfl
"""

from __future__ import annotations

import unittest

from kernel.shelf.sbfl import CAVEAT, SbflError, localize, render

# Classic worked example: line "buggy" is executed by every failing test and few passing.
# t1,t2 fail; t3,t4,t5 pass. "buggy" is in both failing tests + one passing -> most suspicious.
COVERAGE = {
    "t1": {"setup", "buggy", "exit"},
    "t2": {"setup", "buggy", "exit"},
    "t3": {"setup", "safe_a", "exit"},
    "t4": {"setup", "safe_b", "exit"},
    "t5": {"setup", "buggy", "exit"},  # one passing test also hits it
}
OUTCOMES = {"t1": False, "t2": False, "t3": True, "t4": True, "t5": True}


class Ranking(unittest.TestCase):
    def test_faulty_line_ranks_top(self):
        report = localize(COVERAGE, OUTCOMES, formula="ochiai")
        self.assertEqual(report.ranking[0].element, "buggy")

    def test_prime_suspect_is_the_fault(self):
        self.assertEqual(localize(COVERAGE, OUTCOMES).prime_suspects, ("buggy",))

    def test_ubiquitous_lines_rank_below_the_fault(self):
        report = localize(COVERAGE, OUTCOMES, formula="ochiai")
        scores = {s.element: s.score for s in report.ranking}
        # setup/exit run in every test (2 fail, 3 pass); buggy runs in 2 fail, 1 pass
        self.assertGreater(scores["buggy"], scores["setup"])

    def test_line_only_in_passing_tests_scores_zero(self):
        report = localize(COVERAGE, OUTCOMES)
        scores = {s.element: s.score for s in report.ranking}
        self.assertEqual(scores["safe_a"], 0.0)
        self.assertEqual(scores["safe_b"], 0.0)

    def test_ef_ep_counts(self):
        report = localize(COVERAGE, OUTCOMES)
        buggy = next(s for s in report.ranking if s.element == "buggy")
        self.assertEqual((buggy.ef, buggy.ep), (2, 1))


class Formulas(unittest.TestCase):
    def test_every_formula_puts_the_fault_first(self):
        for f in ("ochiai", "tarantula", "dstar", "jaccard", "op2"):
            with self.subTest(formula=f):
                self.assertEqual(
                    localize(COVERAGE, OUTCOMES, formula=f).ranking[0].element, "buggy"
                )

    def test_unknown_formula_refused(self):
        with self.assertRaises(SbflError):
            localize(COVERAGE, OUTCOMES, formula="made_up")

    def test_totals_counted(self):
        report = localize(COVERAGE, OUTCOMES)
        self.assertEqual((report.total_failed, report.total_passed), (2, 3))


class EdgeCases(unittest.TestCase):
    def test_no_failing_tests_localizes_nothing(self):
        report = localize({"t": {"a"}}, {"t": True})
        self.assertEqual(report.prime_suspects, ())
        self.assertTrue(any("no failing tests" in n for n in report.notes))

    def test_coverage_without_outcome_refused(self):
        with self.assertRaises(SbflError):
            localize({"t1": {"a"}}, {})

    def test_all_failing_still_ranks(self):
        report = localize({"t1": {"a", "b"}, "t2": {"a"}}, {"t1": False, "t2": False})
        # 'a' is in both failures, 'b' in one -> 'a' at least as suspicious
        self.assertEqual(report.ranking[0].element, "a")


class Honesty(unittest.TestCase):
    def test_caveat_is_present_and_names_the_study(self):
        report = localize(COVERAGE, OUTCOMES)
        self.assertEqual(report.caveat, CAVEAT)
        self.assertIn("ICSE 2017", report.caveat)

    def test_render_carries_the_caveat_and_suspects(self):
        out = render(localize(COVERAGE, OUTCOMES))
        self.assertIn("CAVEAT", out)
        self.assertIn("suggest-only", out.lower())
        self.assertIn("buggy", out)

    def test_render_reports_no_suspects_when_none(self):
        out = render(localize({"t": {"a"}}, {"t": True}))
        self.assertIn("no suspicious elements", out)


if __name__ == "__main__":
    unittest.main()
