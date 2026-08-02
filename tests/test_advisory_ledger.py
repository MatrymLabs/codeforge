"""Test twin for kernel/advisory_ledger.py (the posture-gap store, RD-2026-0002).

Acceptance (reconcile stamps new/resolved; idempotent; re-open on reappearance), the computations
(oldest-open, MTTR), JSONL round-trip, refusal, and the INTEGRATION: posture's oldest-advisory and
MTTR KPIs go from NOT_COMPUTABLE to MEASURED when the ledger is supplied.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from kernel import advisory_ledger as al
from kernel import posture as p


class Reconcile(unittest.TestCase):
    def test_new_advisory_is_stamped_first_seen(self):
        states = al.reconcile({}, {"PYSEC-1", "PYSEC-2"}, date(2026, 8, 1))
        self.assertEqual(states["PYSEC-1"].first_seen, date(2026, 8, 1))
        self.assertTrue(states["PYSEC-1"].is_open)

    def test_disappeared_advisory_is_resolved(self):
        day1 = al.reconcile({}, {"PYSEC-1"}, date(2026, 8, 1))
        day5 = al.reconcile(day1, set(), date(2026, 8, 5))  # no longer open
        self.assertEqual(day5["PYSEC-1"].resolved, date(2026, 8, 5))
        self.assertFalse(day5["PYSEC-1"].is_open)

    def test_reconcile_is_idempotent(self):
        day1 = al.reconcile({}, {"PYSEC-1"}, date(2026, 8, 1))
        again = al.reconcile(day1, {"PYSEC-1"}, date(2026, 8, 2))
        self.assertEqual(again["PYSEC-1"].first_seen, date(2026, 8, 1))  # unchanged

    def test_reappearing_resolved_advisory_reopens(self):
        day1 = al.reconcile({}, {"PYSEC-1"}, date(2026, 8, 1))
        day5 = al.reconcile(day1, set(), date(2026, 8, 5))  # resolved
        day9 = al.reconcile(day5, {"PYSEC-1"}, date(2026, 8, 9))  # back
        self.assertTrue(day9["PYSEC-1"].is_open)
        self.assertEqual(day9["PYSEC-1"].first_seen, date(2026, 8, 9))  # fresh clock

    def test_reconcile_does_not_mutate_input(self):
        original = al.reconcile({}, {"PYSEC-1"}, date(2026, 8, 1))
        al.reconcile(original, {"PYSEC-1", "PYSEC-2"}, date(2026, 8, 2))
        self.assertNotIn("PYSEC-2", original)  # the input store is untouched


class Computations(unittest.TestCase):
    def _states(self):
        s = al.reconcile({}, {"OLD", "NEW"}, date(2026, 8, 1))
        s = al.reconcile(s, {"OLD", "NEW", "FIXED"}, date(2026, 8, 3))
        return al.reconcile(s, {"OLD", "NEW"}, date(2026, 8, 8))  # FIXED resolved on day 8

    def test_oldest_open_first_seen(self):
        self.assertEqual(al.oldest_open_first_seen(self._states()), date(2026, 8, 1))

    def test_remediation_days_for_resolved(self):
        # FIXED: seen 08-03, resolved 08-08 -> 5 days
        self.assertEqual(al.remediation_days(self._states()), (5,))

    def test_open_count(self):
        self.assertEqual(al.open_count(self._states()), 2)


class IdsFromScan(unittest.TestCase):
    def test_extracts_vuln_ids(self):
        data = {
            "dependencies": [
                {"name": "pip", "vulns": [{"id": "PYSEC-1"}, {"id": "PYSEC-2"}]},
                {"name": "clean", "vulns": []},
            ]
        }
        self.assertEqual(al.ids_from_pip_audit(data), {"PYSEC-1", "PYSEC-2"})


class Persistence(unittest.TestCase):
    def test_save_load_round_trip(self):
        states = al.reconcile({}, {"PYSEC-1"}, date(2026, 8, 1))
        states = al.reconcile(states, set(), date(2026, 8, 5))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "adv.jsonl"
            al.save(path, states)
            self.assertEqual(al.load(path), states)

    def test_absent_file_is_empty_store(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(al.load(Path(d) / "nope.jsonl"), {})

    def test_malformed_line_fails_loud(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "adv.jsonl"
            path.write_text('{"advisory_id": "X"}\n', "utf-8")  # missing first_seen
            with self.assertRaises(al.AdvisoryLedgerError):
                al.load(path)

    def test_blank_lines_are_skipped(self):
        states = al.reconcile({}, {"PYSEC-1"}, date(2026, 8, 1))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "adv.jsonl"
            al.save(path, states)
            path.write_text(path.read_text("utf-8") + "\n\n", "utf-8")  # trailing blanks
            self.assertEqual(al.load(path), states)


class Render(unittest.TestCase):
    def test_render_summarizes_open_and_resolved(self):
        s = al.reconcile({}, {"OPEN", "FIX"}, date(2026, 8, 1))
        s = al.reconcile(s, {"OPEN"}, date(2026, 8, 6))  # FIX resolved (5d)
        out = al.render(s, date(2026, 8, 8))
        self.assertIn("1 open, 1 resolved", out)
        self.assertIn("oldest open advisory exposed 7d", out)
        self.assertIn("MTTR 5.0d", out)

    def test_render_empty(self):
        self.assertIn("0 open", al.render({}, date(2026, 8, 8)))


class PostureIntegration(unittest.TestCase):
    def test_ledger_lights_up_postures_dark_kpis(self):
        with tempfile.TemporaryDirectory() as d:
            # a scan (open advisory) + a ledger with one open + one resolved advisory
            scan = Path(d) / "2026-08-08-pip-audit.json"
            scan.write_text(
                json.dumps({"dependencies": [{"name": "pip", "vulns": [{"id": "OPEN-1"}]}]}),
                "utf-8",
            )
            states = al.reconcile({}, {"OPEN-1"}, date(2026, 8, 1))
            states = al.reconcile(states, {"OPEN-1", "FIXED"}, date(2026, 8, 3))
            states = al.reconcile(states, {"OPEN-1"}, date(2026, 8, 8))  # FIXED resolved (5d)
            ledger = Path(d) / "advisories.jsonl"
            al.save(ledger, states)

            ev = p.load_evidence(d, date(2026, 8, 8), advisory_ledger_path=ledger)
            card = p.scorecard(ev, date(2026, 8, 8))
            by_id = {k.spec.id: k for k in card.kpis}
            # both KPIs that were NOT_COMPUTABLE are now MEASURED
            self.assertEqual(by_id["oldest_open_advisory_days"].status, p.MEASURED)
            self.assertEqual(by_id["oldest_open_advisory_days"].value, 7)  # 08-01 -> 08-08
            self.assertEqual(by_id["mean_time_to_remediate_days"].status, p.MEASURED)
            self.assertEqual(by_id["mean_time_to_remediate_days"].value, 5.0)

    def test_without_ledger_kpis_stay_honestly_not_computable(self):
        with tempfile.TemporaryDirectory() as d:
            scan = Path(d) / "2026-08-08-pip-audit.json"
            scan.write_text(json.dumps({"dependencies": []}), "utf-8")
            card = p.scorecard(p.load_evidence(d, date(2026, 8, 8)), date(2026, 8, 8))
            by_id = {k.spec.id: k for k in card.kpis}
            self.assertEqual(by_id["mean_time_to_remediate_days"].status, p.NOT_COMPUTABLE)


if __name__ == "__main__":
    unittest.main()
