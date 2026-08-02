"""Test twin for repo_report.py. It synthesizes all single-snapshot Lab rungs into one
report, aggregates the right facts, propagates the WEAKEST confidence as overall, and
survives an unparseable module. It is an integration test over the real sibling rungs.

Run:  python3 -m unittest test_repo_report
"""

from __future__ import annotations

import unittest

from kernel.shelf.repo_report import RepoReport, render, synthesize

# a small but full-featured package: architecture (a->b->c), a data model + FSM, a CLI
PKG = {
    "shop.api": (
        "from shop.service import Service\n"
        "import argparse\n"
        "import os\n"
        "def build():\n"
        "    p = argparse.ArgumentParser()\n"
        "    sub = p.add_subparsers()\n"
        "    sub.add_parser('serve')\n"
        "    p.add_argument('--port', default=8080)\n"
        "    return p\n"
        "def config():\n"
        "    return os.getenv('SHOP_DB', 'shop.db')\n"
    ),
    "shop.service": ("from shop.models import Order\ndef place(o):\n    return Order()\n"),
    "shop.models": (
        "from dataclasses import dataclass\n"
        "from enum import Enum\n"
        "class Status(Enum):\n"
        "    OPEN = 'open'\n"
        "    CLOSED = 'closed'\n"
        "@dataclass\n"
        "class Order:\n"
        "    status: Status\n"
        "    def close(self):\n"
        "        self.status = Status.CLOSED\n"
    ),
}


class Synthesis(unittest.TestCase):
    def _r(self) -> RepoReport:
        return synthesize(PKG, package="shop")

    def test_module_count(self):
        self.assertEqual(self._r().module_count, 3)

    def test_architecture_hubs_and_externals(self):
        r = self._r()
        # shop.models and shop.service are imported internally -> non-empty hubs
        self.assertTrue(r.hubs)
        self.assertIn("argparse", r.externals)

    def test_data_model_aggregated(self):
        r = self._r()
        self.assertGreaterEqual(r.entities, 1)  # Order
        self.assertGreaterEqual(r.state_machines, 1)  # Status

    def test_api_surface_counts(self):
        self.assertGreater(self._r().public_symbols, 0)

    def test_invocation_surface(self):
        r = self._r()
        self.assertIn("serve", r.subcommands)
        self.assertIn("SHOP_DB", r.env_vars)

    def test_all_rungs_report_confidence(self):
        keys = set(self._r().rung_confidence)
        self.assertEqual(
            keys,
            {"architecture", "api_surface", "data_model", "health", "invocation"},
        )


class Honesty(unittest.TestCase):
    def test_overall_is_the_minimum_rung(self):
        r = synthesize(PKG, package="shop")
        self.assertEqual(r.overall_confidence, min(r.rung_confidence.values()))

    def test_unparseable_module_does_not_abort(self):
        pkg = dict(PKG)
        pkg["shop.broken"] = "def oops(:\n    pass\n"
        r = synthesize(pkg, package="shop")
        self.assertEqual(r.module_count, 4)
        self.assertLess(r.overall_confidence, 1.0)  # honesty: a blind spot caps the report

    def test_non_dict_fails_loud(self):
        with self.assertRaises(TypeError):
            synthesize(["nope"])


class Rendering(unittest.TestCase):
    def test_render_has_all_sections(self):
        out = render(synthesize(PKG, package="shop"))
        for section in ("ARCHITECTURE", "DATA MODEL", "API SURFACE", "CODE HEALTH", "INVOCATION"):
            self.assertIn(section, out)
        self.assertIn("overall confidence", out)


if __name__ == "__main__":
    unittest.main()
