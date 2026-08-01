"""Test twin for control_flow.py. It profiles each function's branches, loops, handlers,
nesting depth, exits, guard-style and generator-ness; shortlists complex functions; and
refuses to crash on bad source.

Run:  python3 -m unittest test_control_flow
"""

from __future__ import annotations

import unittest

from parts.shelf.control_flow import ControlFlowError, analyze, render

SAMPLE = """
def linear(a):
    return a + 1


def guarded(a):
    if a is None:
        return 0
    return a * 2


def nested(items):
    total = 0
    for x in items:
        if x > 0:
            for y in range(x):
                if y % 2:
                    total += y
    return total


def risky():
    try:
        return work()
    except ValueError:
        raise
    except KeyError:
        return None


def stream(n):
    for i in range(n):
        yield i


class Box:
    def get(self, k):
        return k
"""


class Profiles(unittest.TestCase):
    def _byname(self):
        return {p.qualname: p for p in analyze(SAMPLE, module="m").functions}

    def test_all_functions_and_methods_profiled(self):
        names = set(self._byname())
        self.assertEqual(names, {"linear", "guarded", "nested", "risky", "stream", "Box.get"})

    def test_linear_style(self):
        p = self._byname()["linear"]
        self.assertEqual(p.guard_style, "linear")
        self.assertEqual(p.branch_points, 0)
        self.assertEqual(p.exit_points, 1)

    def test_guard_clause_style(self):
        self.assertEqual(self._byname()["guarded"].guard_style, "guard-clauses")

    def test_nested_depth_and_style(self):
        p = self._byname()["nested"]
        self.assertGreaterEqual(p.max_depth, 3)
        self.assertEqual(p.guard_style, "nested")
        self.assertEqual(p.loops, 2)

    def test_exception_handlers_counted(self):
        p = self._byname()["risky"]
        self.assertEqual(p.handlers, 2)
        self.assertGreaterEqual(p.exit_points, 3)  # return, raise, return

    def test_generator_detected(self):
        self.assertTrue(self._byname()["stream"].is_generator)
        self.assertFalse(self._byname()["linear"].is_generator)


class Complexity(unittest.TestCase):
    def test_deep_function_shortlisted(self):
        report = analyze(SAMPLE, module="m")
        self.assertIn("nested", report.complex_functions)

    def test_simple_function_not_shortlisted(self):
        report = analyze(SAMPLE, module="m")
        self.assertNotIn("linear", report.complex_functions)

    def test_nested_def_yield_does_not_mark_outer_generator(self):
        src = "def outer():\n    def inner():\n        yield 1\n    return inner\n"
        p = {x.qualname: x for x in analyze(src).functions}
        self.assertFalse(p["outer"].is_generator)


class RenderAndRefusal(unittest.TestCase):
    def test_render_readable(self):
        out = render(analyze(SAMPLE, module="m"))
        self.assertIn("control flow: m", out)
        self.assertIn("REVIEW-FIRST", out)

    def test_empty_module_is_not_error(self):
        self.assertEqual(analyze("x = 1\n").functions, ())

    def test_syntax_error_fails_loud(self):
        with self.assertRaises(ControlFlowError):
            analyze("def bad(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
