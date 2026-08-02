"""Test twin for risk_router.py. The property under test: risk drives review depth,
and high-risk signals (auth/secrets/migrations) floor the band regardless of score.

Run:  python3 -m unittest test_risk_router
"""

from __future__ import annotations

import unittest

from kernel.shelf.risk_router import (
    CRITICAL,
    HIGH,
    LOW,
    MEDIUM,
    Change,
    RiskError,
    route,
    score,
)


class Scoring(unittest.TestCase):
    def test_trivial_change_is_low(self):
        r = route(Change(files_touched=1))
        self.assertEqual(r.band, LOW)
        self.assertEqual(r.required_approvals, 1)
        self.assertFalse(r.require_security_review)

    def test_auth_change_floors_to_high(self):
        # a tiny diff, but it touches auth -> HIGH regardless of the low score
        r = route(Change(files_touched=1, touches_auth=True))
        self.assertIn(r.band, (HIGH, CRITICAL))
        self.assertEqual(r.required_approvals, 2)
        self.assertTrue(r.require_security_review)

    def test_secrets_floor_and_security_review(self):
        r = route(Change(touches_secrets=True))
        self.assertIn(r.band, (HIGH, CRITICAL))
        self.assertTrue(r.require_security_review)

    def test_migrations_floor(self):
        self.assertIn(route(Change(touches_migrations=True)).band, (HIGH, CRITICAL))

    def test_stacked_signals_reach_critical(self):
        c = Change(
            touches_auth=True, touches_secrets=True, touches_migrations=True, added_dependencies=2
        )
        r = route(c)
        self.assertEqual(r.band, CRITICAL)
        self.assertTrue(r.require_security_review)

    def test_dependencies_and_findings_raise_score(self):
        self.assertGreater(score(Change(added_dependencies=3, scan_findings=3)), score(Change()))

    def test_medium_band(self):
        # ci/deploy alone is 20 pts -> just under high, above medium? tune with deps
        r = route(Change(touches_ci_or_deploy=True, added_dependencies=1))  # 20 + 10 = 30
        self.assertEqual(r.band, MEDIUM)

    def test_ai_authored_is_noted(self):
        r = route(Change(ai_authored=True))
        self.assertTrue(any("AI-authored" in reason for reason in r.reasons))

    def test_score_capped_at_100(self):
        c = Change(
            touches_auth=True,
            touches_secrets=True,
            touches_migrations=True,
            touches_ci_or_deploy=True,
            added_dependencies=10,
            scan_findings=10,
            ai_authored=True,
        )
        self.assertLessEqual(score(c), 100)


class Refusal(unittest.TestCase):
    def test_negative_counts_rejected(self):
        with self.assertRaises(RiskError):
            Change(added_dependencies=-1)

    def test_bad_thresholds(self):
        with self.assertRaises(RiskError):
            route(Change(), high_at=90, critical_at=50)


if __name__ == "__main__":
    unittest.main()
