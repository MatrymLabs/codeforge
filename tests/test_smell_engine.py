"""Test twin for smell_engine.py. Each detector fires on a real smell and stays quiet
on clean code; every finding names its refactoring; bad input fails loud.

Run:  python3 -m unittest test_smell_engine
"""

from __future__ import annotations

import unittest

from kernel.shelf.smell_engine import SmellError, Thresholds, analyze, smell_ids


def ids(source: str, **kw) -> set[str]:
    return {s.smell_id for s in analyze(source, **kw)}


class Clean(unittest.TestCase):
    def test_clean_code_is_quiet(self):
        src = "def add(a, b):\n    return a + b\n"
        self.assertEqual(analyze(src), [])

    def test_allowed_numbers_not_magic(self):
        self.assertNotIn("SMELL.MAGIC_NUMBER", ids("x = 0\ny = 1\nz = 2\n"))


class Detectors(unittest.TestCase):
    def test_long_method(self):
        body = "\n".join(f"    a{i} = {i} + 3" for i in range(30))
        self.assertIn(
            "SMELL.LONG_METHOD",
            ids(f"def f():\n{body}\n", thresholds=Thresholds(max_method_statements=25)),
        )

    def test_long_parameter_list(self):
        self.assertIn(
            "SMELL.LONG_PARAMETER_LIST", ids("def f(a, b, c, d, e, f, g):\n    return a\n")
        )

    def test_self_not_counted_as_param(self):
        self.assertNotIn(
            "SMELL.LONG_PARAMETER_LIST",
            ids("class C:\n    def m(self, a, b, c, d, e):\n        return a\n"),
        )

    def test_magic_number(self):
        self.assertIn("SMELL.MAGIC_NUMBER", ids("timeout = 3600\n"))

    def test_mutable_default_arg(self):
        self.assertIn("SMELL.MUTABLE_DEFAULT_ARG", ids("def f(x=[]):\n    return x\n"))

    def test_boolean_flag_arg(self):
        self.assertIn("SMELL.BOOLEAN_FLAG_ARG", ids("def render(fast=True):\n    return fast\n"))

    def test_bare_except(self):
        self.assertIn("SMELL.BARE_EXCEPT", ids("try:\n    x = 1\nexcept:\n    pass\n"))

    def test_swallowed_exception(self):
        found = ids("try:\n    x = 1\nexcept ValueError:\n    pass\n")
        self.assertIn("SMELL.SWALLOWED_EXCEPTION", found)

    def test_too_many_returns(self):
        body = "\n".join(f"    if x == {i}: return {i}" for i in range(7))
        self.assertIn(
            "SMELL.TOO_MANY_RETURNS",
            ids(f"def f(x):\n{body}\n", thresholds=Thresholds(max_returns=5)),
        )

    def test_high_complexity(self):
        body = "\n".join(f"    if x == {i}:\n        y = {i}" for i in range(12))
        self.assertIn(
            "SMELL.HIGH_COMPLEXITY",
            ids(f"def f(x):\n{body}\n", thresholds=Thresholds(max_complexity=10)),
        )

    def test_deep_nesting(self):
        src = (
            "def f(x):\n    if x:\n        for i in x:\n            while i:\n"
            "                with i:\n                    if i:\n                        return i\n"
        )
        self.assertIn("SMELL.DEEP_NESTING", ids(src, thresholds=Thresholds(max_nesting=4)))

    def test_large_class(self):
        methods = "\n".join(f"    def m{i}(self):\n        return {i} + 5" for i in range(21))
        self.assertIn(
            "ANTIPATTERN.GOD_OBJECT",
            ids(f"class C:\n{methods}\n", thresholds=Thresholds(max_class_methods=20)),
        )

    def test_duplicate_function_body(self):
        block = "    a = 1\n    b = 2\n    c = a + b\n    d = c * 3\n    return d"
        src = f"def f():\n{block}\ndef g():\n{block}\n"
        self.assertIn("SMELL.DUPLICATE_CODE", ids(src))


class Coverage(unittest.TestCase):
    def test_detects_at_least_ten_smell_types(self):
        # the corpus roadmap Stage 1 threshold: >= 10 smell types
        self.assertGreaterEqual(len(smell_ids()), 10)

    def test_every_finding_names_a_refactoring(self):
        smells = analyze("def f(x=[]):\n    timeout = 3600\n    return x\n")
        self.assertTrue(smells)
        self.assertTrue(all(s.refactoring for s in smells))


class Refusal(unittest.TestCase):
    def test_syntax_error_fails_loud(self):
        with self.assertRaises(SmellError):
            analyze("def oops(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
