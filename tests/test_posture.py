"""Test twin for kernel/posture.py (RD-2026-0002 #5).

The point is HONESTY: a KPI is measured from real evidence or declared not_computable with the
store that would enable it - never a faked zero. Acceptance (each measurable KPI computes + breaches
its target correctly), the not_computable path (absent evidence names its gap, does not crash),
metadata completeness (every catalog spec carries the anti-gaming fields), and refusal (malformed
scan evidence fails loud).
"""

from __future__ import annotations

import unittest
from datetime import date

from kernel import posture as p

_TODAY = date(2026, 8, 2)


def _full_evidence() -> p.PostureEvidence:
    return p.PostureEvidence(
        latest_scan_date=date(2026, 8, 1),
        open_advisory_count=0,
        oldest_advisory_first_seen=date(2026, 8, 1),
        remediation_days=(2, 4, 6),
        expired_exceptions=0,
        sbom_present=True,
        scan_cadence_days=1,
    )


class Measured(unittest.TestCase):
    def test_a_fresh_clean_posture_has_no_breaches(self):
        card = p.scorecard(_full_evidence(), _TODAY)
        self.assertEqual(card.measured, 6)
        self.assertEqual(card.breaches, ())

    def test_stale_evidence_breaches_freshness(self):
        ev = p.PostureEvidence(latest_scan_date=date(2026, 7, 8), scan_cadence_days=1)
        card = p.scorecard(ev, _TODAY)
        fresh = next(k for k in card.kpis if k.spec.id == "evidence_freshness_days")
        self.assertEqual(fresh.value, 25)
        self.assertTrue(fresh.breaches_target)

    def test_open_advisories_breach_the_zero_target(self):
        ev = p.PostureEvidence(latest_scan_date=_TODAY, open_advisory_count=5)
        card = p.scorecard(ev, _TODAY)
        adv = next(k for k in card.kpis if k.spec.id == "open_advisory_count")
        self.assertEqual(adv.value, 5)
        self.assertTrue(adv.breaches_target)

    def test_mttr_averages_deployed_fix_days(self):
        ev = p.PostureEvidence(remediation_days=(2, 4, 6))
        mttr = next(k for k in p.compute(ev, _TODAY) if k.spec.id == "mean_time_to_remediate_days")
        self.assertEqual(mttr.status, p.MEASURED)
        self.assertEqual(mttr.value, 4.0)

    def test_missing_sbom_breaches(self):
        ev = p.PostureEvidence(sbom_present=False)
        sbom = next(k for k in p.compute(ev, _TODAY) if k.spec.id == "sbom_release_coverage")
        self.assertTrue(sbom.breaches_target)


class Honesty(unittest.TestCase):
    def test_absent_evidence_is_not_computable_not_a_faked_zero(self):
        card = p.scorecard(p.PostureEvidence(), _TODAY)
        # empty evidence -> most KPIs are not_computable, and NONE are silently "0/passing"
        self.assertGreaterEqual(len(card.not_computable), 4)
        for k in card.not_computable:
            self.assertIsNone(k.value)
            self.assertTrue(k.detail)  # names the missing store

    def test_mttr_names_the_missing_store(self):
        mttr = next(
            k
            for k in p.compute(p.PostureEvidence(), _TODAY)
            if k.spec.id == "mean_time_to_remediate_days"
        )
        self.assertEqual(mttr.status, p.NOT_COMPUTABLE)
        self.assertIn("remediation store", mttr.detail)

    def test_scorecard_note_flags_uncomputed_kpis(self):
        card = p.scorecard(p.PostureEvidence(), _TODAY)
        self.assertTrue(any("not yet computable" in n for n in card.notes))


class Metadata(unittest.TestCase):
    def test_every_spec_carries_the_anti_gaming_fields(self):
        for spec in p.KPI_CATALOG:
            self.assertTrue(
                spec.scope and spec.data_source and spec.target and spec.owner,
                f"{spec.id} is missing anti-gaming metadata",
            )

    def test_catalog_ids_are_unique(self):
        ids = [s.id for s in p.KPI_CATALOG]
        self.assertEqual(len(ids), len(set(ids)))


class LoadAndRender(unittest.TestCase):
    def test_load_empty_dir_is_honest_not_an_error(
        self,
    ):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ev = p.load_evidence(d, _TODAY)
            self.assertIsNone(ev.latest_scan_date)  # no scan -> freshness not_computable downstream

    def test_load_parses_advisory_count_and_date(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            scan = Path(d) / "2026-07-08-pip-audit.json"
            scan.write_text(
                json.dumps(
                    {
                        "dependencies": [
                            {"name": "pip", "vulns": [{"id": "PYSEC-1"}, {"id": "PYSEC-2"}]},
                            {"name": "clean", "vulns": []},
                        ]
                    }
                ),
                "utf-8",
            )
            ev = p.load_evidence(d, _TODAY)
            self.assertEqual(ev.latest_scan_date, date(2026, 7, 8))
            self.assertEqual(ev.open_advisory_count, 2)

    def test_malformed_scan_fails_loud(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "2026-07-08-pip-audit.json").write_text("{not json", "utf-8")
            with self.assertRaises(p.PostureError):
                p.load_evidence(d, _TODAY)

    def test_render_shows_measured_and_not_computable(self):
        out = p.render(
            p.scorecard(p.PostureEvidence(latest_scan_date=_TODAY, open_advisory_count=0), _TODAY)
        )
        self.assertIn("security posture:", out)
        self.assertIn("NOT COMPUTABLE", out)


class MutationKillRate(unittest.TestCase):
    """The AP-09 KPI: a mutation score is MEASURED from a fresh recorded run, NOT_COMPUTABLE (never
    a faked zero) when there is no run or it is stale, and it breaches the 70% floor honestly."""

    def _run(self, killed: int, survived: int, run_date: date):
        from kernel.shelf.mutation_kpi import MutationResult

        return MutationResult(
            total=killed + survived, killed=killed, survived=survived, run_date=run_date
        )

    def test_measured_and_breaches_below_the_floor(self):
        # the real fleet baseline: 122/179 killed = 68%, honestly under the 70% target
        ev = p.PostureEvidence(mutation_result=self._run(122, 57, _TODAY))
        mut = next(k for k in p.compute(ev, _TODAY) if k.spec.id == "mutation_kill_rate")
        self.assertEqual(mut.status, p.MEASURED)
        self.assertEqual(mut.value, 0.682)
        self.assertTrue(mut.breaches_target)

    def test_measured_and_passes_above_the_floor(self):
        ev = p.PostureEvidence(mutation_result=self._run(150, 29, _TODAY))
        mut = next(k for k in p.compute(ev, _TODAY) if k.spec.id == "mutation_kill_rate")
        self.assertEqual(mut.status, p.MEASURED)
        self.assertFalse(mut.breaches_target)

    def test_no_run_is_not_computable_and_names_the_recorder(self):
        mut = next(
            k for k in p.compute(p.PostureEvidence(), _TODAY) if k.spec.id == "mutation_kill_rate"
        )
        self.assertEqual(mut.status, p.NOT_COMPUTABLE)
        self.assertIsNone(mut.value)
        self.assertIn("make mutation", mut.detail)

    def test_stale_run_is_not_computable(self):
        from datetime import timedelta

        ev = p.PostureEvidence(mutation_result=self._run(150, 29, _TODAY - timedelta(days=45)))
        mut = next(k for k in p.compute(ev, _TODAY) if k.spec.id == "mutation_kill_rate")
        self.assertEqual(mut.status, p.NOT_COMPUTABLE)
        self.assertIn("stale", mut.detail)

    def test_load_evidence_reads_a_recorded_run_from_the_dir(self):
        import tempfile
        from pathlib import Path

        from kernel import mutation_recorder as mr

        with tempfile.TemporaryDirectory() as d:
            mr.record(self._run(122, 57, _TODAY), Path(d) / "mutation-latest.json")
            ev = p.load_evidence(d, _TODAY)  # no pip-audit scan present; mutation still lights up
            self.assertIsNotNone(ev.mutation_result)
            mut = next(k for k in p.compute(ev, _TODAY) if k.spec.id == "mutation_kill_rate")
            self.assertEqual(mut.status, p.MEASURED)


if __name__ == "__main__":
    unittest.main()
