"""Test twin for kernel/refactor.py. Without LibCST (CI): the behavioural gate is exercised
via a monkeypatched scoped_rename - a clean transform is applied, a behaviour-changing one
is REFUSED with a counterexample. With the [refactor] extra installed: scope-correctness
(the binding + its uses rename, globals and other scopes do not), plus the refusals
(unparsable, missing function, unknown name, bad identifier, collision).

Run:  python3 -m unittest test_refactor
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from kernel.refactor import (
    RefactorError,
    RefactorResult,
    refactor_available,
    scoped_rename,
    verified_rename,
)

_HAS_LIBCST = refactor_available()
_needs_libcst = unittest.skipUnless(
    _HAS_LIBCST, "optional dependency libcst ([refactor] extra) not installed"
)

SRC = (
    "x = 100\n\n"
    "def f(x):\n"
    "    y = x + 1\n"
    "    return x * y + helper(x)\n\n"
    "def h(x):\n"
    "    return x - 1\n\n"
    "def helper(a):\n"
    "    return a\n"
)


class BehaviouralGate(unittest.TestCase):
    """Runs WITHOUT LibCST - the gate is the stdlib sampler; scoped_rename is mocked."""

    def test_clean_transform_is_applied(self):
        same = "def g(x: int) -> int:\n    return x * 2 + 1\n"
        with patch("kernel.refactor.scoped_rename", return_value=same):
            r = verified_rename(same, "g", "x", "y")
        self.assertTrue(r.applied)
        self.assertEqual(r.verdict, "preserved")
        self.assertEqual(r.source, same)

    def test_behaviour_changing_transform_is_refused(self):
        before = "def g(x: int) -> int:\n    return x * 2\n"
        broken = "def g(x: int) -> int:\n    return x * 3\n"  # a codemod bug a gate must catch
        with patch("kernel.refactor.scoped_rename", return_value=broken):
            r = verified_rename(before, "g", "x", "y", samples=500)
        self.assertFalse(r.applied)
        self.assertEqual(r.verdict, "broken")
        self.assertIsNotNone(r.counterexample)
        self.assertEqual(r.source, before)  # refused -> ORIGINAL returned, never the bad code
        self.assertIsInstance(r, RefactorResult)

    def test_available_returns_bool(self):
        self.assertIsInstance(refactor_available(), bool)


@_needs_libcst
class ScopeCorrect(unittest.TestCase):
    def test_param_and_its_uses_rename(self):
        out = scoped_rename(SRC, "f", "x", "value")
        self.assertIn("def f(value):", out)
        self.assertIn("return value * y + helper(value)", out)

    def test_global_of_same_name_untouched(self):
        self.assertIn("x = 100", scoped_rename(SRC, "f", "x", "value"))

    def test_same_name_in_other_function_untouched(self):
        self.assertIn("def h(x):", scoped_rename(SRC, "f", "x", "value"))

    def test_local_variable_renames(self):
        src = "def f():\n    total = 0\n    total = total + 1\n    return total\n"
        out = scoped_rename(src, "f", "total", "acc")
        self.assertIn("acc = 0", out)
        self.assertIn("return acc", out)
        self.assertNotIn("total", out)

    def test_formatting_and_comments_preserved(self):
        src = "def f(x):\n    # keep me\n    return x  +  1  # trailing\n"
        out = scoped_rename(src, "f", "x", "y")
        self.assertIn("# keep me", out)
        self.assertIn("+  1  # trailing", out)  # LibCST is lossless

    def test_verified_clean_rename_is_applied_and_preserved(self):
        r = verified_rename(SRC, "f", "x", "value")
        self.assertTrue(r.applied)
        self.assertEqual(r.verdict, "preserved")
        self.assertIn("def f(value):", r.source)


@_needs_libcst
class Refusals(unittest.TestCase):
    def test_unparsable_source_refused(self):
        with self.assertRaises(RefactorError):
            scoped_rename("def f(x):\n    return x +\n", "f", "x", "y")

    def test_missing_function_refused(self):
        with self.assertRaises(RefactorError):
            scoped_rename(SRC, "nope", "x", "y")

    def test_unknown_name_refused(self):
        with self.assertRaises(RefactorError):
            scoped_rename(SRC, "f", "zzz", "y")

    def test_bad_new_identifier_refused(self):
        with self.assertRaises(RefactorError):
            scoped_rename(SRC, "f", "x", "1nope")

    def test_collision_with_existing_name_refused(self):
        # renaming param x to y collides with the local y already in f
        with self.assertRaises(RefactorError):
            scoped_rename(SRC, "f", "x", "y")


if __name__ == "__main__":
    unittest.main()
