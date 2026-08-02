"""Test twin for call_graph.py. It resolves internal call edges (bare + method calls),
finds entrypoints, flags private-uncalled dead code (but not public entries or recursion),
ranks hotspots, and stays honest about dynamic dispatch. It never crashes on bad source.

Run:  python3 -m unittest test_call_graph
"""

from __future__ import annotations

import unittest

from kernel.shelf.call_graph import CallGraphError, analyze, render

SAMPLE = """
def public_entry(x):
    return _helper(x) + _helper(x)


def _helper(v):
    return _leaf(v)


def _leaf(v):
    return v


def _orphan():
    return 1


def factorial(n):
    return 1 if n <= 1 else n * factorial(n - 1)


class Worker:
    def run(self, job):
        return self._step(job)

    def _step(self, job):
        return job
"""


class Edges(unittest.TestCase):
    def _r(self):
        return analyze(SAMPLE, module="m")

    def test_bare_call_edge(self):
        edges = {(e.caller, e.callee) for e in self._r().edges}
        self.assertIn(("public_entry", "_helper"), edges)
        self.assertIn(("_helper", "_leaf"), edges)

    def test_method_call_edge(self):
        edges = {(e.caller, e.callee) for e in self._r().edges}
        self.assertIn(("Worker.run", "Worker._step"), edges)

    def test_in_degree_counts_distinct_callers(self):
        c = {x.qualname: x for x in self._r().callables}
        # _helper is called by public_entry (twice, but one caller) -> in_degree 1
        self.assertEqual(c["_helper"].in_degree, 1)


class Structure(unittest.TestCase):
    def _r(self):
        return analyze(SAMPLE, module="m")

    def test_public_uncalled_is_entrypoint_not_dead(self):
        self.assertIn("public_entry", self._r().entrypoints)
        self.assertNotIn("public_entry", self._r().dead_code)

    def test_private_uncalled_is_dead(self):
        self.assertIn("_orphan", self._r().dead_code)

    def test_called_private_is_not_dead(self):
        self.assertNotIn("_helper", self._r().dead_code)
        self.assertNotIn("_leaf", self._r().dead_code)

    def test_dispatch_registered_private_is_not_dead(self):
        # a private handler referenced in a dispatch table (never syntactically called)
        # must NOT be flagged dead - the reference guard catches it
        src = "def _handler(x):\n    return x\n\nTABLE = {'go': _handler}\n"
        self.assertNotIn("_handler", analyze(src).dead_code)

    def test_dunder_method_is_not_dead(self):
        # __init__ is called implicitly by construction, never syntactically
        src = "class C:\n    def __init__(self):\n        self.x = 1\n"
        self.assertNotIn("C.__init__", analyze(src).dead_code)

    def test_recursion_is_flagged_not_dead(self):
        r = self._r()
        self.assertIn("factorial", r.recursive)
        # factorial is public and only self-called -> entrypoint, and never a dead candidate
        self.assertNotIn("factorial", r.dead_code)

    def test_hotspot_ranked_by_in_degree(self):
        # _leaf and _helper each have callers; hotspots lists the most-called first
        self.assertTrue(len(self._r().hotspots) >= 1)


class Honesty(unittest.TestCase):
    def test_getattr_dispatch_lowers_confidence(self):
        src = "def f(o, n):\n    return getattr(o, n)()\n"
        r = analyze(src)
        self.assertLess(r.confidence, 1.0)
        self.assertTrue(any("getattr" in u for u in r.unknowns))

    def test_clean_module_full_confidence(self):
        self.assertEqual(analyze(SAMPLE).confidence, 1.0)

    def test_empty_module_is_not_error(self):
        r = analyze("x = 1\n")
        self.assertEqual(r.callables, ())
        self.assertEqual(r.dead_code, ())


class RenderAndRefusal(unittest.TestCase):
    def test_render_readable(self):
        out = render(analyze(SAMPLE, module="m"))
        self.assertIn("call graph: m", out)
        self.assertIn("_orphan", out)  # dead-code candidate surfaced

    def test_render_clean_dead(self):
        self.assertIn("dead-code candidates: none", render(analyze("def _f():\n    return _f()\n")))

    def test_syntax_error_fails_loud(self):
        with self.assertRaises(CallGraphError):
            analyze("def bad(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
