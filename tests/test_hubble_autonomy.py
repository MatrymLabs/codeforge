"""Test twin for kernel/hubble/autonomy.py (RD-2026-0002 #13).

The policy CAPS authority, never raises it. Acceptance (no triggers -> executor allowed; a trigger
lowers the cap; the lowest cap wins under conflict; production-without-rollback forbids executor),
the permits() yes/no + reasons, and refusal of an unknown mode.
"""

from __future__ import annotations

import unittest

from kernel.hubble import autonomy as a


class MaxAllowed(unittest.TestCase):
    def test_no_triggers_allows_executor(self):
        mode, reasons = a.max_allowed(set())
        self.assertEqual(mode, a.EXECUTOR)

    def test_security_sensitive_caps_at_reviewer(self):
        mode, _ = a.max_allowed({"security_sensitive"})
        self.assertEqual(mode, a.REVIEWER)

    def test_production_without_rollback_forbids_executor_and_reviewer(self):
        mode, _ = a.max_allowed({"production_without_tested_rollback"})
        self.assertEqual(mode, a.ASSISTANT)

    def test_lowest_cap_wins_under_conflict(self):
        # reviewer-cap + assistant-cap both active -> assistant (the safe default)
        mode, reasons = a.max_allowed({"security_sensitive", "production_without_tested_rollback"})
        self.assertEqual(mode, a.ASSISTANT)
        self.assertTrue(any("production" in r for r in reasons))


class Permits(unittest.TestCase):
    def test_requesting_within_the_cap_is_permitted(self):
        v = a.permits(a.REVIEWER, {"security_sensitive"})
        self.assertTrue(v.permitted)
        self.assertEqual(v.allowed_mode, a.REVIEWER)

    def test_requesting_above_the_cap_is_denied_with_reason(self):
        v = a.permits(a.EXECUTOR, {"security_sensitive"})
        self.assertFalse(v.permitted)
        self.assertEqual(v.allowed_mode, a.REVIEWER)
        self.assertTrue(v.reasons)

    def test_assistant_is_always_permitted(self):
        self.assertTrue(a.permits(a.ASSISTANT, {"production_without_tested_rollback"}).permitted)

    def test_render_shows_permitted_or_denied(self):
        self.assertIn("DENIED", a.render(a.permits(a.EXECUTOR, {"security_sensitive"})))
        self.assertIn("PERMITTED", a.render(a.permits(a.ASSISTANT, set())))


class Refusal(unittest.TestCase):
    def test_unknown_mode_fails_loud(self):
        with self.assertRaises(a.AutonomyError):
            a.permits("god_mode", set())

    def test_a_trigger_with_a_bad_max_mode_fails_loud(self):
        with self.assertRaises(a.AutonomyError):
            a.Trigger("x", "superuser", "no")


if __name__ == "__main__":
    unittest.main()
