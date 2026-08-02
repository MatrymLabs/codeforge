"""Test twin for kernel/hubble/grounding.py (RD-2026-0002 #15).

The producer feeds the retrieval_grounding dimension the decision gate escalates on. Acceptance
(all-grounded passes; one ungrounded fails the finding), that decide() then ESCALATES on it (the
producer/consumer loop closes), the real filesystem resolver (path + ast symbol), and refusal.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kernel.hubble import grounding as g
from kernel.hubble.diagnosis import ESCALATE, DiagnosticFinding, decide


class Producer(unittest.TestCase):
    def test_all_grounded_claims_pass(self):
        claims = [g.Claim("reuses cursor", "kernel/shelf/cursor.py")]
        finding = g.check_grounding(claims, lambda c: True)
        self.assertTrue(finding.passed)
        self.assertEqual(finding.dimension, "retrieval_grounding")

    def test_one_ungrounded_claim_fails_the_finding(self):
        claims = [g.Claim("real", "a.py"), g.Claim("made up", "ghost.py")]
        resolver = lambda c: c.path != "ghost.py"  # noqa: E731
        finding = g.check_grounding(claims, resolver)
        self.assertFalse(finding.passed)
        self.assertIn("ghost.py", finding.note)

    def test_empty_claims_pass_nothing_asserted(self):
        self.assertTrue(g.check_grounding([], lambda c: False).passed)

    def test_the_finding_makes_decide_escalate(self):
        # closes the producer -> consumer loop: an ungrounded claim forces escalation
        finding = g.check_grounding([g.Claim("x", "ghost.py")], lambda c: False)
        other = DiagnosticFinding("static", True, 1.0)
        decision = decide([finding, other])
        self.assertEqual(decision.action, ESCALATE)
        self.assertEqual(decision.escalation_class, "retrieval_grounding")


class FilesystemResolver(unittest.TestCase):
    def test_resolves_path_and_symbol(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("def real_fn():\n    return 1\n", "utf-8")
            resolve = g.filesystem_resolver(d)
            self.assertTrue(resolve(g.Claim("has fn", "m.py", "real_fn")))
            self.assertFalse(resolve(g.Claim("missing sym", "m.py", "nope")))
            self.assertFalse(resolve(g.Claim("missing file", "gone.py")))

    def test_existing_file_without_a_named_symbol_resolves(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("x = 1\n", "utf-8")
            self.assertTrue(g.filesystem_resolver(d)(g.Claim("just the file", "m.py")))

    def test_an_unparseable_file_does_not_resolve_a_symbol(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("def broken(:\n", "utf-8")
            self.assertFalse(g.filesystem_resolver(d)(g.Claim("c", "m.py", "broken")))

    def test_symbol_in_a_comment_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.py").write_text("# ghost_fn is only mentioned here\nx = 1\n", "utf-8")
            self.assertFalse(g.filesystem_resolver(d)(g.Claim("c", "m.py", "ghost_fn")))


class Refusal(unittest.TestCase):
    def test_a_claim_with_no_path_fails_loud(self):
        with self.assertRaises(g.GroundingError):
            g.Claim("no citation", "   ")


if __name__ == "__main__":
    unittest.main()
