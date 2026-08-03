"""Test twin for kernel/mutation_recorder.py (AP-09 follow-up, RD-2026-0003).

The recorder is the disk seam around the pure shelf part: it must round-trip a run faithfully,
parse a real-shaped cosmic-ray cr-report, read an absent file as honest None (not a crash, not a
faked zero), and refuse a corrupt file LOUD. Acceptance + refusal, with hostile inputs.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from kernel import mutation_recorder as mr
from kernel.shelf.mutation_kpi import MutationResult

# A verified-real cr-report summary shape (mirrors the shelf adapter's fixture), with survivors.
_CR_REPORT = """\
[skipped mutant detail lines ...]
total jobs: 179
complete: 179 (100.00%)
surviving mutants: 57 (31.84%)
"""


class RoundTrip(unittest.TestCase):
    def test_record_then_load_is_faithful(self):
        run = MutationResult(total=179, killed=122, survived=57, run_date=date(2026, 8, 2))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mutation-latest.json"
            mr.record(run, path)
            back = mr.load(path)
        self.assertEqual(back, run)  # frozen dataclass equality: every field survived the trip

    def test_record_creates_missing_parent_dirs(self):
        run = MutationResult(total=4, killed=4, survived=0, run_date=date(2026, 8, 2))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "security-evidence" / "mutation-latest.json"
            written = mr.record(run, path)
            self.assertTrue(written.exists())

    def test_record_cr_report_parses_the_real_shape(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mutation-latest.json"
            run = mr.record_cr_report(_CR_REPORT, date(2026, 8, 2), path)
            self.assertEqual(run.total, 179)
            self.assertEqual(run.survived, 57)
            self.assertEqual(run.killed, 122)  # complete(179) - surviving(57)
            self.assertEqual(mr.load(path), run)


class Honesty(unittest.TestCase):
    def test_absent_file_is_none_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(mr.load(Path(d) / "nope.json"))

    def test_empty_file_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mutation-latest.json"
            path.write_text("   \n", "utf-8")
            self.assertIsNone(mr.load(path))

    def test_corrupt_json_fails_loud(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mutation-latest.json"
            path.write_text("{not json", "utf-8")
            with self.assertRaises(mr.MutationEvidenceError):
                mr.load(path)

    def test_missing_field_fails_loud(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mutation-latest.json"
            path.write_text('{"total": 10, "killed": 8, "run_date": "2026-08-02"}', "utf-8")
            with self.assertRaises(mr.MutationEvidenceError):
                mr.load(path)  # no "survived" key

    def test_incoherent_counts_fail_loud(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mutation-latest.json"
            # survived+killed exceeds total: the MutationResult invariant must reject it on load
            path.write_text(
                '{"total": 5, "killed": 4, "survived": 4, "run_date": "2026-08-02"}', "utf-8"
            )
            with self.assertRaises(mr.MutationEvidenceError):
                mr.load(path)


if __name__ == "__main__":
    unittest.main()
