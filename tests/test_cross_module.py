"""Test twin for cross_module.py. It resolves cross-module symbol usage (from-import +
module-alias attribute), finds package-wide unused public API, ranks cross-module hubs,
separates externals, and stays honest about dynamic imports. It never crashes on a bad
module.

Run:  python3 -m unittest test_cross_module
"""

from __future__ import annotations

import unittest

from kernel.shelf.cross_module import CrossModuleError, analyze_repo, render

# pkg.api uses helper.build (from-import) and util.clamp (module-alias); orphan is unused
PKG = {
    "pkg.api": (
        "from pkg.helper import build\n"
        "import pkg.util\n"
        "def handle():\n"
        "    return build() + pkg.util.clamp(3)\n"
    ),
    "pkg.helper": "def build():\n    return 1\n\ndef orphan():\n    return 2\n",
    "pkg.util": "import os\ndef clamp(n):\n    return max(0, n)\n",
}


class Usage(unittest.TestCase):
    def _r(self):
        return analyze_repo(PKG, package="pkg")

    def test_from_import_usage_edge(self):
        edges = {(e.src, e.dst, e.symbol) for e in self._r().edges}
        self.assertIn(("pkg.api", "pkg.helper", "build"), edges)

    def test_module_alias_attribute_usage_edge(self):
        edges = {(e.src, e.dst, e.symbol) for e in self._r().edges}
        self.assertIn(("pkg.api", "pkg.util", "clamp"), edges)

    def test_used_by_is_recorded(self):
        by_sym = {s.symbol: s for s in self._r().symbols}
        self.assertEqual(by_sym["pkg.helper:build"].used_by, ("pkg.api",))

    def test_external_import_recorded(self):
        self.assertIn("os", self._r().externals)


class UnusedPublic(unittest.TestCase):
    def _r(self):
        return analyze_repo(PKG, package="pkg")

    def test_unused_public_symbol_flagged(self):
        self.assertIn("pkg.helper:orphan", self._r().unused_public)

    def test_used_symbol_not_flagged(self):
        self.assertNotIn("pkg.helper:build", self._r().unused_public)
        self.assertNotIn("pkg.util:clamp", self._r().unused_public)

    def test_private_symbols_are_not_tracked(self):
        pkg = {"p.a": "def _hidden():\n    return 1\n"}
        r = analyze_repo(pkg, package="p")
        self.assertEqual(r.symbols, ())  # underscore names are not public API

    def test_self_use_does_not_count(self):
        # a symbol used only within its OWN module is still unused cross-module
        pkg = {"p.a": "def f():\n    return 1\ndef g():\n    return f()\n"}
        r = analyze_repo(pkg, package="p")
        self.assertIn("p.a:f", r.unused_public)


class Hubs(unittest.TestCase):
    def test_hub_ranked_by_cross_module_users(self):
        pkg = {
            "p.core": "def shared():\n    return 1\n",
            "p.a": "from p.core import shared\nx = shared()\n",
            "p.b": "from p.core import shared\ny = shared()\n",
        }
        r = analyze_repo(pkg, package="p")
        self.assertIn("p.core:shared", r.hubs)
        by = {s.symbol: s for s in r.symbols}
        self.assertEqual(set(by["p.core:shared"].used_by), {"p.a", "p.b"})


class Honesty(unittest.TestCase):
    def test_dynamic_import_lowers_confidence(self):
        pkg = {"p.a": "import importlib\ndef f(n):\n    return importlib.import_module(n)\n"}
        r = analyze_repo(pkg, package="p")
        self.assertLess(r.confidence, 1.0)
        self.assertTrue(any("import_module" in u for u in r.unknowns))

    def test_star_import_is_unknown(self):
        pkg = {"p.a": "from p.b import *\n", "p.b": "def thing():\n    return 1\n"}
        r = analyze_repo(pkg, package="p")
        self.assertTrue(any("star import" in u for u in r.unknowns))

    def test_unparseable_module_is_not_fatal(self):
        pkg = {"p.a": "def broken(:\n    pass\n", "p.b": "def ok():\n    return 1\n"}
        r = analyze_repo(pkg, package="p")
        self.assertTrue(any("could not parse" in u for u in r.unknowns))
        self.assertIn("p.b:ok", {s.symbol for s in r.symbols})

    def test_clean_package_full_confidence(self):
        self.assertEqual(analyze_repo(PKG, package="pkg").confidence, 1.0)


class RenderAndRefusal(unittest.TestCase):
    def test_render_readable(self):
        out = render(analyze_repo(PKG, package="pkg"))
        self.assertIn("cross-module: pkg", out)
        self.assertIn("pkg.helper:orphan", out)

    def test_non_dict_fails_loud(self):
        with self.assertRaises(CrossModuleError):
            analyze_repo(["nope"])


if __name__ == "__main__":
    unittest.main()
