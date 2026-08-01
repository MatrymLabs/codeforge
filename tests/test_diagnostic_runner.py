"""Test twin for diagnostic_runner.py. The central property under test: an
escalation-class failure is NON-OVERRIDABLE - no confidence score demotes it.

Run:  python3 -m unittest test_diagnostic_runner
"""

from __future__ import annotations

import unittest

from parts.shelf.diagnostic_runner import (
    ESCALATE,
    PROCEED,
    REVISE,
    STOP,
    Check,
    DiagnosticError,
    decide,
)


def passing(kind: str, n: int, **kw) -> list[Check]:
    return [Check(f"{kind}{i}", kind, True, **kw) for i in range(n)]


class Routing(unittest.TestCase):
    def test_all_pass_proceeds(self):
        v = decide(passing("static", 5))
        self.assertEqual(v.decision, PROCEED)
        self.assertEqual(v.confidence, 1.0)
        self.assertFalse(v.escalated)

    def test_mid_confidence_revises(self):
        checks = passing("static", 7) + [Check("s1", "static", False), Check("s2", "static", False)]
        v = decide(checks)  # 7/9 ~= 0.78 -> between revise(0.6) and proceed(0.85)
        self.assertEqual(v.decision, REVISE)

    def test_low_confidence_stops(self):
        checks = passing("static", 1) + [Check(f"f{i}", "static", False) for i in range(4)]
        v = decide(checks)  # 1/5 = 0.2 -> below revise
        self.assertEqual(v.decision, STOP)


class NonOverridableEscalation(unittest.TestCase):
    def test_one_failed_security_check_escalates_despite_high_confidence(self):
        # 99 passing + 1 failed security: confidence ~0.99 but MUST escalate
        checks = passing("static", 99) + [Check("authz", "security", False)]
        v = decide(checks)
        self.assertEqual(v.decision, ESCALATE)
        self.assertTrue(v.escalated)
        self.assertGreater(v.confidence, 0.9)  # score is high, yet overridden
        self.assertTrue(any("security" in r for r in v.reasons))

    def test_blocking_escalation_class_stops(self):
        checks = passing("static", 50) + [Check("sandbox", "sandbox", False, severity="blocking")]
        self.assertEqual(decide(checks).decision, STOP)

    def test_grounding_failure_escalates(self):
        checks = passing("static", 10) + [Check("citations", "grounding", False)]
        self.assertEqual(decide(checks).decision, ESCALATE)

    def test_custom_escalation_classes(self):
        checks = passing("static", 10) + [Check("data", "data", False)]
        v = decide(checks, escalation_classes=frozenset({"data"}))
        self.assertEqual(v.decision, ESCALATE)

    def test_blocking_non_escalation_failure_stops(self):
        checks = passing("static", 10) + [Check("build", "static", False, severity="blocking")]
        v = decide(checks)
        self.assertEqual(v.decision, STOP)
        self.assertFalse(v.escalated)  # a hard stop, not an escalation


class Refusal(unittest.TestCase):
    def test_empty_checks(self):
        with self.assertRaises(DiagnosticError):
            decide([])

    def test_bad_thresholds(self):
        with self.assertRaises(DiagnosticError):
            decide(passing("static", 1), proceed_threshold=0.5, revise_threshold=0.9)

    def test_bad_severity(self):
        with self.assertRaises(DiagnosticError):
            Check("x", "static", True, severity="fatal")

    def test_bad_weight(self):
        with self.assertRaises(DiagnosticError):
            Check("x", "static", True, weight=0)

    def test_empty_name(self):
        with self.assertRaises(DiagnosticError):
            Check("", "static", True)


if __name__ == "__main__":
    unittest.main()
