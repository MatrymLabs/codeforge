"""Test twin for repo_analyzer.py. It resolves the internal import graph correctly,
finds real cycles, ranks hubs/entrypoints/leaves, separates external deps, and stays
honest about dynamic imports it cannot follow. It never crashes on a bad module.

Run:  python3 -m unittest test_repo_analyzer
"""

from __future__ import annotations

import unittest

from parts.shelf.repo_analyzer import RepoAnalyzerError, analyze_repo, render

# a tiny 4-module package: app -> service -> repo (leaf); util is imported by service
PKG = {
    "app.main": "from app.service import Service\nimport os\n",
    "app.service": "from app.repo import Repo\nfrom app.util import helper\n",
    "app.repo": "import sqlite3\n",
    "app.util": "def helper():\n    return 1\n",
}


class Graph(unittest.TestCase):
    def _m(self):
        return analyze_repo(PKG, package="app")

    def test_internal_edges_resolved(self):
        edges = {(e.src, e.dst) for e in self._m().edges}
        self.assertIn(("app.main", "app.service"), edges)
        self.assertIn(("app.service", "app.repo"), edges)
        self.assertIn(("app.service", "app.util"), edges)

    def test_external_imports_are_not_edges(self):
        edges = {(e.src, e.dst) for e in self._m().edges}
        self.assertNotIn(("app.repo", "sqlite3"), edges)
        self.assertIn("sqlite3", self._m().externals)
        self.assertIn("os", self._m().externals)

    def test_entrypoint_is_the_unimported_module(self):
        self.assertEqual(self._m().entrypoints, ("app.main",))

    def test_leaves_import_nothing_internal(self):
        self.assertEqual(set(self._m().leaves), {"app.repo", "app.util"})

    def test_fan_in_and_hub(self):
        nodes = {n.module: n for n in self._m().nodes}
        self.assertEqual(nodes["app.service"].fan_in, 1)
        self.assertEqual(nodes["app.service"].fan_out, 2)
        self.assertIn("app.service", self._m().hubs)

    def test_acyclic_package_has_no_cycles(self):
        self.assertEqual(self._m().cycles, ())
        self.assertEqual(self._m().confidence, 1.0)


class RelativeImports(unittest.TestCase):
    def test_relative_import_resolves_to_sibling(self):
        pkg = {
            "app.a": "from .b import thing\n",
            "app.b": "x = 1\n",
        }
        edges = {(e.src, e.dst) for e in analyze_repo(pkg, package="app").edges}
        self.assertIn(("app.a", "app.b"), edges)

    def test_parent_relative_import(self):
        pkg = {
            "app.sub.a": "from ..core import c\n",
            "app.core": "y = 2\n",
        }
        edges = {(e.src, e.dst) for e in analyze_repo(pkg, package="app").edges}
        self.assertIn(("app.sub.a", "app.core"), edges)

    def test_relative_escaping_root_is_an_unknown(self):
        pkg = {"app.a": "from ... import wild\n"}
        m = analyze_repo(pkg, package="app")
        self.assertTrue(any("escapes the package root" in u for u in m.unknowns))


class Cycles(unittest.TestCase):
    def test_two_module_cycle_is_found(self):
        pkg = {
            "p.a": "from p.b import B\n",
            "p.b": "from p.a import A\n",
        }
        m = analyze_repo(pkg, package="p")
        self.assertEqual(m.cycles, (("p.a", "p.b"),))
        self.assertLess(m.confidence, 1.0)

    def test_three_module_cycle(self):
        pkg = {
            "p.a": "from p.b import B\n",
            "p.b": "from p.c import C\n",
            "p.c": "from p.a import A\n",
        }
        self.assertEqual(analyze_repo(pkg, package="p").cycles, (("p.a", "p.b", "p.c"),))

    def test_self_import_is_not_a_cycle_edge(self):
        # a module importing itself is dropped (no self-edge), so no false cycle
        pkg = {"p.a": "from p.a import thing\n"}
        self.assertEqual(analyze_repo(pkg, package="p").cycles, ())


class Honesty(unittest.TestCase):
    def test_dynamic_import_lowers_confidence(self):
        pkg = {"p.a": "import importlib\ndef f(name):\n    return importlib.import_module(name)\n"}
        m = analyze_repo(pkg, package="p")
        self.assertLess(m.confidence, 1.0)
        self.assertTrue(any("import_module" in u for u in m.unknowns))

    def test_unparseable_module_is_a_node_but_not_fatal(self):
        pkg = {"p.a": "def broken(:\n    pass\n", "p.b": "x = 1\n"}
        m = analyze_repo(pkg, package="p")
        nodes = {n.module: n for n in m.nodes}
        self.assertFalse(nodes["p.a"].parse_ok)
        self.assertTrue(nodes["p.b"].parse_ok)
        self.assertTrue(any("could not parse" in u for u in m.unknowns))

    def test_confidence_never_below_floor(self):
        pkg = {f"p.m{i}": f"from p.m{(i + 1) % 30} import x\n" for i in range(30)}
        self.assertGreaterEqual(analyze_repo(pkg, package="p").confidence, 0.3)


class RenderAndRefusal(unittest.TestCase):
    def test_render_is_readable(self):
        out = render(analyze_repo(PKG, package="app"))
        self.assertIn("app.service", out)
        self.assertIn("acyclic", out)

    def test_render_shows_cycles(self):
        pkg = {"p.a": "from p.b import B\n", "p.b": "from p.a import A\n"}
        self.assertIn("IMPORT CYCLES", render(analyze_repo(pkg, package="p")))

    def test_non_dict_input_fails_loud(self):
        with self.assertRaises(RepoAnalyzerError):
            analyze_repo(["not", "a", "dict"])


if __name__ == "__main__":
    unittest.main()
