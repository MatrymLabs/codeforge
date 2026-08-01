"""Test twin for parts/verify_smt.py. Without the optional crosshair-tool (CI), it covers
the parse/refusal paths and the loud "dependency absent" contract; with crosshair installed,
it proves a rare-input divergence BROKEN (the needle the sampler misses) and a rename
PRESERVED. The symbolic cases skip when the extra is not installed, so CI stays green.

Run:  python3 -m unittest test_verify_smt
"""

from __future__ import annotations

import importlib.util
import unittest
from dataclasses import FrozenInstanceError

from parts.verify_smt import Outcome, SmtVerdict, VerifySmtError, verify_transform_smt

_HAS_CROSSHAIR = importlib.util.find_spec("crosshair") is not None

# The needle a random sampler cannot draw; a proof-grade gate must catch it.
RARE_BEFORE = "def f(x: int) -> int:\n    return x * 2\n"
RARE_AFTER = "def f(x: int) -> int:\n    if x == 987654321:\n        return -1\n    return x * 2\n"
RENAME_BEFORE = "def f(x: int) -> int:\n    return x * 2 + 1\n"
RENAME_AFTER = "def f(y: int) -> int:\n    return y * 2 + 1\n"


class ParseRefusal(unittest.TestCase):
    """These run WITHOUT crosshair - they refuse before the dependency is ever needed."""

    def test_unparsable_before_refused(self):
        with self.assertRaises(VerifySmtError):
            verify_transform_smt("def f(x: int) ->\n", RENAME_AFTER, "f")

    def test_missing_function_refused(self):
        with self.assertRaises(VerifySmtError):
            verify_transform_smt(RENAME_BEFORE, RENAME_AFTER, "nope")

    def test_error_type_is_a_value_error(self):
        self.assertTrue(issubclass(VerifySmtError, ValueError))


@unittest.skipIf(_HAS_CROSSHAIR, "exercises the dependency-absent path; crosshair IS installed")
class DependencyAbsent(unittest.TestCase):
    def test_valid_input_without_crosshair_fails_loud(self):
        # Parsing succeeds, so the call reaches the lazy import and must raise a clear error.
        with self.assertRaises(VerifySmtError) as ctx:
            verify_transform_smt(RENAME_BEFORE, RENAME_AFTER, "f")
        self.assertIn("verify", str(ctx.exception).lower())


@unittest.skipUnless(_HAS_CROSSHAIR, "optional dependency crosshair-tool not installed")
class SymbolicVerdict(unittest.TestCase):
    def test_rare_divergence_is_proved_broken(self):
        v = verify_transform_smt(RARE_BEFORE, RARE_AFTER, "f")
        self.assertIs(v.outcome, Outcome.BROKEN)
        self.assertIsNotNone(v.counterexample)
        self.assertEqual(v.counterexample["args"], {"x": "987654321"})

    def test_behavior_preserving_rename_is_preserved(self):
        v = verify_transform_smt(RENAME_BEFORE, RENAME_AFTER, "f")
        self.assertIs(v.outcome, Outcome.PRESERVED)
        self.assertIsNone(v.counterexample)

    def test_verdict_is_frozen_and_carries_caveat(self):
        v = verify_transform_smt(RENAME_BEFORE, RENAME_AFTER, "f")
        self.assertIn("not a proof", v.caveat.lower())
        self.assertIsInstance(v, SmtVerdict)
        with self.assertRaises(FrozenInstanceError):
            v.outcome = Outcome.BROKEN


if __name__ == "__main__":
    unittest.main()
