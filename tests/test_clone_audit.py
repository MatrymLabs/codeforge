"""Test twin for kernel/clone_audit.py. Functions that are structurally identical modulo local
names land in one family; genuinely different functions do not; trivial stubs are filtered;
unparsable files are skipped (not fatal); bad parameters are refused; the caveat rides on the
report and render.

Run:  python3 -m unittest test_clone_audit
"""

from __future__ import annotations

import unittest

from kernel.clone_audit import (
    CAVEAT,
    CloneAuditError,
    CloneReport,
    find_clones,
    render,
    scan_paths,
)

# Two clones (same shape, different local names) + one genuinely different function.
CLONE_A = (
    "def scale_up(value):\n"
    "    total = 0\n"
    "    for item in value:\n"
    "        total = total + item\n"
    "    return total\n"
)
CLONE_B = (
    "def accumulate(seq):\n"
    "    acc = 0\n"
    "    for element in seq:\n"
    "        acc = acc + element\n"
    "    return acc\n"
)
DIFFERENT = (
    "def longest(words):\n"
    "    best = ''\n"
    "    for w in words:\n"
    "        if len(w) > len(best):\n"
    "            best = w\n"
    "    return best\n"
)


class Grouping(unittest.TestCase):
    def test_renamed_clones_share_a_family(self):
        report = find_clones({"a.py": CLONE_A, "b.py": CLONE_B})
        self.assertEqual(len(report.families), 1)
        fam = report.families[0]
        self.assertEqual(len(fam.members), 2)
        self.assertEqual({m.name for m in fam.members}, {"scale_up", "accumulate"})
        self.assertEqual({m.file for m in fam.members}, {"a.py", "b.py"})

    def test_different_functions_are_not_grouped(self):
        report = find_clones({"a.py": CLONE_A, "c.py": DIFFERENT})
        self.assertEqual(report.families, ())
        self.assertEqual(report.functions_scanned, 2)

    def test_three_way_clone_family_ranks_first(self):
        report = find_clones({"a.py": CLONE_A, "b.py": CLONE_B, "d.py": CLONE_A + "\n" + DIFFERENT})
        self.assertEqual(
            report.families[0].members.__len__(), 3
        )  # a, b, d all share scale_up shape

    def test_methods_in_classes_are_scanned_and_match(self):
        # Two identical methods in two classes: dedented + content-addressed, they clone-match.
        src_x = (
            "class X:\n"
            "    def go(self, value):\n"
            "        total = 0\n"
            "        for i in value:\n"
            "            total = total + i\n"
            "        return total\n"
        )
        src_y = (
            "class Y:\n"
            "    def run(self, seq):\n"
            "        acc = 0\n"
            "        for e in seq:\n"
            "            acc = acc + e\n"
            "        return acc\n"
        )
        report = find_clones({"x.py": src_x, "y.py": src_y})
        self.assertEqual(len(report.families), 1)
        self.assertEqual({m.name for m in report.families[0].members}, {"go", "run"})


class Filtering(unittest.TestCase):
    def test_trivial_functions_are_filtered(self):
        stubs = {
            "s1.py": "def a():\n    return None\n",
            "s2.py": "def b():\n    return None\n",
        }
        # both are 1-statement stubs -> below the default floor -> not reported
        self.assertEqual(find_clones(stubs).families, ())

    def test_min_statements_is_tunable(self):
        stubs = {"s1.py": "def a():\n    return None\n", "s2.py": "def b():\n    return None\n"}
        report = find_clones(stubs, min_statements=1)
        self.assertEqual(len(report.families), 1)  # now the stubs count as a clone family

    def test_unparsable_file_is_skipped_not_fatal(self):
        report = find_clones({"ok.py": CLONE_A, "bad.py": "def f(:\n"})
        self.assertEqual(len(report.skipped), 1)
        self.assertIn("bad.py", report.skipped[0])
        self.assertEqual(report.files_scanned, 1)


class Refusal(unittest.TestCase):
    def test_zero_min_statements_refused(self):
        with self.assertRaises(CloneAuditError):
            find_clones({"a.py": CLONE_A}, min_statements=0)


class Honesty(unittest.TestCase):
    def test_caveat_present_and_names_structural(self):
        report = find_clones({"a.py": CLONE_A, "b.py": CLONE_B})
        self.assertEqual(report.caveat, CAVEAT)
        self.assertIn("not proof", report.caveat.lower())
        self.assertIsInstance(report, CloneReport)

    def test_render_carries_caveat_and_families(self):
        text = render(find_clones({"a.py": CLONE_A, "b.py": CLONE_B}))
        self.assertIn("caveat:", text)
        self.assertIn("clone families", text)
        self.assertIn("scale_up", text)

    def test_render_reports_skipped_files(self):
        text = render(find_clones({"ok.py": CLONE_A, "bad.py": "def f(:\n"}))
        self.assertIn("skipped 1 unparsable file", text)


class ScanPaths(unittest.TestCase):
    def test_scan_paths_reads_a_real_tree(self):
        import tempfile  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.py").write_text(CLONE_A, encoding="utf-8")
            (root / "b.py").write_text(CLONE_B, encoding="utf-8")
            (root / "c.py").write_text(DIFFERENT, encoding="utf-8")
            report = scan_paths([root])
        self.assertEqual(len(report.families), 1)
        self.assertGreaterEqual(report.files_scanned, 3)


if __name__ == "__main__":
    unittest.main()
