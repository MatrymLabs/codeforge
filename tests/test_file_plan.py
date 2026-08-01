"""Test twin for file_plan.py. A canonical repo scores 1.0 and passes; a missing LICENSE
or a committed .env fails a blocking rule; globs match src-layout/CI/tests; the score is
weighted; custom plans and malformed rules are handled; scan reads a real tmp dir.

Run:  python3 -m unittest test_file_plan
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from parts.shelf.file_plan import FilePlanError, FilePlanRule, check, render, scan

CANONICAL = {
    "README.md",
    "LICENSE",
    "pyproject.toml",
    ".gitignore",
    "CHANGELOG.md",
    "tests/test_thing.py",
    ".github/workflows/ci.yml",
    "src/mypkg/__init__.py",
}


class Compliance(unittest.TestCase):
    def test_canonical_repo_passes_with_full_score(self):
        report = check(CANONICAL)
        self.assertTrue(report.passed)
        self.assertEqual(report.score, 1.0)
        self.assertEqual(report.failures, ())

    def test_missing_license_is_a_blocking_failure(self):
        paths = CANONICAL - {"LICENSE"}
        report = check(paths)
        self.assertFalse(report.passed)
        self.assertTrue(any(f.rule_id == "fp.license" for f in report.blocking_failures))

    def test_committed_env_is_a_blocking_failure(self):
        report = check(CANONICAL | {".env"})
        self.assertFalse(report.passed)
        self.assertTrue(any(f.rule_id == "fp.no-committed-env" for f in report.blocking_failures))

    def test_missing_changelog_is_info_not_blocking(self):
        report = check(CANONICAL - {"CHANGELOG.md"})
        self.assertTrue(report.passed)  # info severity does not block
        self.assertLess(report.score, 1.0)  # but it costs score

    def test_legacy_setup_py_flagged_absent_rule(self):
        report = check(CANONICAL | {"setup.py"})
        self.assertTrue(any(f.rule_id == "fp.no-setup-py" and not f.ok for f in report.findings))


class Matching(unittest.TestCase):
    def test_glob_matches_ci_and_tests(self):
        report = check(CANONICAL)
        by_id = {f.rule_id: f for f in report.findings}
        self.assertTrue(by_id["fp.ci"].ok)
        self.assertTrue(by_id["fp.tests"].ok)

    def test_any_of_accepts_alternative_license_names(self):
        report = check((CANONICAL - {"LICENSE"}) | {"COPYING"})
        by_id = {f.rule_id: f for f in report.findings}
        self.assertTrue(by_id["fp.license"].ok)

    def test_absent_rule_passes_when_file_missing(self):
        by_id = {f.rule_id: f for f in check(CANONICAL).findings}
        self.assertTrue(by_id["fp.no-setup-py"].ok)  # no setup.py -> rule satisfied


class Scoring(unittest.TestCase):
    def test_score_is_weighted(self):
        # dropping the high-weight pyproject (1.5) costs more than dropping changelog (0.5)
        drop_pyproject = check(CANONICAL - {"pyproject.toml"}).score
        drop_changelog = check(CANONICAL - {"CHANGELOG.md"}).score
        self.assertLess(drop_pyproject, drop_changelog)

    def test_custom_plan(self):
        plan = (FilePlanRule("only.readme", "readme", "present", ("README.md",), "error", 1.0),)
        self.assertTrue(check({"README.md"}, plan).passed)
        self.assertFalse(check({"other.txt"}, plan).passed)


class Refusal(unittest.TestCase):
    def test_unknown_kind_refused(self):
        with self.assertRaises(FilePlanError):
            FilePlanRule("bad", "x", "teleport", ("a",))

    def test_empty_targets_refused(self):
        with self.assertRaises(FilePlanError):
            FilePlanRule("bad", "x", "present", ())

    def test_empty_plan_refused(self):
        with self.assertRaises(FilePlanError):
            check(CANONICAL, ())

    def test_render_readable(self):
        out = render(check(CANONICAL - {"LICENSE"}))
        self.assertIn("[FAIL]", out)
        self.assertIn("fp.license", out)


class RealScan(unittest.TestCase):
    def test_scan_reads_a_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "README.md").write_text("hi")
            (root / "pyproject.toml").write_text("[project]\n")
            (root / "src" / "pkg").mkdir(parents=True)
            (root / "src" / "pkg" / "__init__.py").write_text("")
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref")  # must be ignored
            paths = scan(root)
        self.assertIn("README.md", paths)
        self.assertIn("src/pkg/__init__.py", paths)
        self.assertNotIn(".git/HEAD", paths)  # ignored dir


if __name__ == "__main__":
    unittest.main()
