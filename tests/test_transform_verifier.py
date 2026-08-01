"""Test twin for transform_verifier.py. It confirms a behavior-preserving transform passes
(scope-correct rename), a subtly-broken transform is caught with a counterexample
(off-by-one, wrong operator), syntax/missing-function transforms are BROKEN, exception
behavior is compared, non-determinism is honestly INCONCLUSIVE, and malformed input is
refused. The honesty caveat rides on every verdict.

Run:  python3 -m unittest test_transform_verifier
"""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from parts.shelf.transform_verifier import (
    CAVEAT,
    Outcome,
    TransformVerifierError,
    Verdict,
    render,
    verify_transform,
)

# A real function and a scope-correct rename of its parameter (behavior-preserving).
BEFORE = "def f(x):\n    return x * 2 + 1\n"
RENAMED = "def f(y):\n    return y * 2 + 1\n"  # same behavior, renamed binding
OFF_BY_ONE = "def f(x):\n    return x * 2 + 2\n"  # BROKEN: +1 -> +2
WRONG_OP = "def f(x):\n    return x * 2 - 1\n"  # BROKEN: + -> -
SYNTAX_BAD = "def f(x):\n    return x * 2 +\n"  # BROKEN: won't parse
RENAMED_AWAY = "def g(x):\n    return x * 2 + 1\n"  # BROKEN: function no longer named f


class Preserved(unittest.TestCase):
    def test_scope_correct_rename_is_preserved(self):
        v = verify_transform(BEFORE, RENAMED, "f")
        self.assertIs(v.outcome, Outcome.PRESERVED)
        self.assertTrue(v.preserved)
        self.assertIsNone(v.counterexample)
        self.assertGreater(v.samples_run, 0)

    def test_identity_transform_is_preserved(self):
        self.assertIs(verify_transform(BEFORE, BEFORE, "f").outcome, Outcome.PRESERVED)

    def test_preserving_exception_behavior(self):
        # Both raise ZeroDivisionError on x == 0; a rename must keep that.
        before = "def d(x):\n    return 10 // x\n"
        after = "def d(z):\n    return 10 // z\n"
        self.assertIs(verify_transform(before, after, "d").outcome, Outcome.PRESERVED)


class Broken(unittest.TestCase):
    def test_off_by_one_is_caught_with_counterexample(self):
        v = verify_transform(BEFORE, OFF_BY_ONE, "f")
        self.assertIs(v.outcome, Outcome.BROKEN)
        self.assertIsNotNone(v.counterexample)
        self.assertIn("args", v.counterexample)

    def test_wrong_operator_is_caught(self):
        self.assertIs(verify_transform(BEFORE, WRONG_OP, "f").outcome, Outcome.BROKEN)

    def test_syntax_error_transform_is_broken_not_raised(self):
        v = verify_transform(BEFORE, SYNTAX_BAD, "f")
        self.assertIs(v.outcome, Outcome.BROKEN)
        self.assertFalse(v.parses)
        self.assertEqual(v.samples_run, 0)

    def test_function_renamed_away_is_broken(self):
        v = verify_transform(BEFORE, RENAMED_AWAY, "f")
        self.assertIs(v.outcome, Outcome.BROKEN)
        self.assertTrue(v.parses)  # it parses; the function just isn't there

    def test_changed_exception_type_is_caught(self):
        # BEFORE raises on 0; AFTER guards it and returns 0 -> divergence on x == 0.
        before = "def d(x):\n    return 10 // x\n"
        after = "def d(x):\n    return 0 if x == 0 else 10 // x\n"
        self.assertIs(verify_transform(before, after, "d").outcome, Outcome.BROKEN)


class Inconclusive(unittest.TestCase):
    def test_non_deterministic_before_is_inconclusive(self):
        before = "import random\ndef r(x):\n    return random.random() + x\n"
        after = "import random\ndef r(y):\n    return random.random() + y\n"
        v = verify_transform(before, after, "r")
        self.assertIs(v.outcome, Outcome.INCONCLUSIVE)
        self.assertTrue(any("non-deterministic" in n for n in v.notes))


class Refusal(unittest.TestCase):
    def test_unparsable_before_refused(self):
        with self.assertRaises(TransformVerifierError):
            verify_transform("def f(x):\n    return x +\n", RENAMED, "f")

    def test_missing_function_in_before_refused(self):
        with self.assertRaises(TransformVerifierError):
            verify_transform(BEFORE, RENAMED, "does_not_exist")

    def test_zero_samples_refused(self):
        with self.assertRaises(TransformVerifierError):
            verify_transform(BEFORE, RENAMED, "f", samples=0)


class Reproducibility(unittest.TestCase):
    def test_same_seed_same_verdict(self):
        v1 = verify_transform(BEFORE, OFF_BY_ONE, "f", seed=42)
        v2 = verify_transform(BEFORE, OFF_BY_ONE, "f", seed=42)
        self.assertEqual(v1.counterexample, v2.counterexample)

    def test_no_arg_function_notes_single_call(self):
        before = "def c():\n    return 42\n"
        v = verify_transform(before, before, "c")
        self.assertIs(v.outcome, Outcome.PRESERVED)
        self.assertTrue(any("single call" in n for n in v.notes))


class Honesty(unittest.TestCase):
    def test_caveat_present_and_names_sampling(self):
        v = verify_transform(BEFORE, RENAMED, "f")
        self.assertEqual(v.caveat, CAVEAT)
        self.assertIn("not a proof", v.caveat.lower())

    def test_render_carries_caveat(self):
        text = render(verify_transform(BEFORE, OFF_BY_ONE, "f"))
        self.assertIn("caveat:", text)
        self.assertIn("BROKEN", text)

    def test_verdict_is_frozen(self):
        v = verify_transform(BEFORE, RENAMED, "f")
        with self.assertRaises(FrozenInstanceError):
            v.outcome = Outcome.BROKEN
        self.assertIsInstance(v, Verdict)


if __name__ == "__main__":
    unittest.main()
