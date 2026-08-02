"""Test twin for hotspots.py. The churny-AND-complex file ranks top; stable-complex and
churny-simple rank low; only files with both history and code are ranked; the git-log
parser counts commits per file; complexity is McCabe from AST; the caveat rides along.

Run:  python3 -m unittest test_hotspots
"""

from __future__ import annotations

import unittest

from kernel.shelf.hotspots import (
    CAVEAT,
    HotspotError,
    churn_from_log,
    complexity_from_sources,
    rank,
    render,
)


class Ranking(unittest.TestCase):
    def test_churny_and_complex_ranks_top(self):
        churn = {"hot.py": 50, "stable.py": 1, "simple.py": 60}
        cx = {"hot.py": 40, "stable.py": 45, "simple.py": 2}
        report = rank(churn, cx)
        self.assertEqual(report.prime_hotspot, "hot.py")

    def test_stable_complex_and_churny_simple_rank_below(self):
        churn = {"hot.py": 50, "stable.py": 1, "simple.py": 60}
        cx = {"hot.py": 40, "stable.py": 45, "simple.py": 2}
        scores = {h.path: h.score for h in rank(churn, cx).hotspots}
        self.assertGreater(scores["hot.py"], scores["stable.py"])
        self.assertGreater(scores["hot.py"], scores["simple.py"])

    def test_score_is_product_of_normalized_factors(self):
        # the max-churn max-complexity file scores 1.0
        report = rank({"a": 10, "b": 5}, {"a": 20, "b": 4})
        top = report.hotspots[0]
        self.assertEqual(top.path, "a")
        self.assertEqual(top.score, 1.0)

    def test_top_limit(self):
        churn = {f"f{i}.py": i + 1 for i in range(30)}
        cx = {f"f{i}.py": i + 1 for i in range(30)}
        self.assertEqual(len(rank(churn, cx, top=5).hotspots), 5)


class SharedFilesOnly(unittest.TestCase):
    def test_only_files_in_both_maps_are_ranked(self):
        report = rank({"a.py": 5, "onlychurn.py": 9}, {"a.py": 3, "onlycode.py": 8})
        paths = {h.path for h in report.hotspots}
        self.assertEqual(paths, {"a.py"})
        self.assertEqual(report.file_count, 1)

    def test_skipped_files_are_noted(self):
        report = rank({"a.py": 5, "onlychurn.py": 9}, {"a.py": 3, "onlycode.py": 8})
        joined = " ".join(report.notes)
        self.assertIn("no measured complexity", joined)
        self.assertIn("no change history", joined)

    def test_no_shared_files_is_empty_not_error(self):
        report = rank({"x.py": 1}, {"y.py": 1})
        self.assertEqual(report.hotspots, ())
        self.assertEqual(report.prime_hotspot, "")


class ChurnFromLog(unittest.TestCase):
    def test_counts_commits_per_file(self):
        log = (
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"  # 40-char hash
            "src/app.py\n"
            "README.md\n"
            "\n"
            "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5\n"  # another hash
            "src/app.py\n"
        )
        churn = churn_from_log(log)
        self.assertEqual(churn["src/app.py"], 2)
        self.assertEqual(churn["README.md"], 1)

    def test_same_file_twice_in_one_commit_counts_once(self):
        log = "a" * 40 + "\ndup.py\ndup.py\n"
        self.assertEqual(churn_from_log(log)["dup.py"], 1)


class ComplexityFromSources(unittest.TestCase):
    def test_more_branches_more_complexity(self):
        simple = "def f(x):\n    return x\n"
        branchy = (
            "def f(x):\n"
            "    if x > 0:\n"
            "        for i in range(x):\n"
            "            if i % 2 and i > 1:\n"
            "                return i\n"
            "    return 0\n"
        )
        cx = complexity_from_sources({"simple.py": simple, "branchy.py": branchy})
        self.assertGreater(cx["branchy.py"], cx["simple.py"])

    def test_unparseable_file_skipped(self):
        cx = complexity_from_sources({"good.py": "x = 1\n", "bad.py": "def (:\n"})
        self.assertIn("good.py", cx)
        self.assertNotIn("bad.py", cx)


class Honesty(unittest.TestCase):
    def test_caveat_present(self):
        self.assertEqual(rank({"a": 1}, {"a": 1}).caveat, CAVEAT)
        self.assertIn("PRIORITIZATION", CAVEAT)

    def test_render_carries_caveat_and_hotspot(self):
        out = render(rank({"hot.py": 9, "x.py": 1}, {"hot.py": 9, "x.py": 1}))
        self.assertIn("CAVEAT", out)
        self.assertIn("hot.py", out)

    def test_render_no_hotspots(self):
        self.assertIn("no hotspots", render(rank({"x.py": 1}, {"y.py": 1})))

    def test_non_dict_refused(self):
        with self.assertRaises(HotspotError):
            rank([("a", 1)], {"a": 1})


if __name__ == "__main__":
    unittest.main()
