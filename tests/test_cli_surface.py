"""Test twin for cli_surface.py. It extracts argparse subcommands + options (required,
default), environment reads (getenv/environ.get/environ[...]), flags a non-argparse
framework honestly, and refuses to crash on bad source.

Run:  python3 -m unittest test_cli_surface
"""

from __future__ import annotations

import unittest

from parts.shelf.cli_surface import CliSurfaceError, analyze, render

SAMPLE = """
import argparse
import os


def build():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    serve = sub.add_parser("serve")
    serve.add_argument("--port", default=4000)
    play = sub.add_parser("play")
    parser.add_argument("target")
    parser.add_argument("-v", "--verbose", required=False)
    return parser


def config():
    host = os.getenv("CODEFORGE_HOST", "localhost")
    db = os.environ["CODEFORGE_DB"]
    token = os.environ.get("API_TOKEN")
    return host, db, token
"""


class Cli(unittest.TestCase):
    def _r(self):
        return analyze(SAMPLE, module="cli")

    def test_subcommands(self):
        self.assertEqual(set(self._r().subcommands), {"serve", "play"})

    def test_positional_is_required(self):
        opts = {o.flags: o for o in self._r().options}
        self.assertTrue(opts[("target",)].required)
        self.assertTrue(opts[("target",)].positional)

    def test_optional_flag_not_required(self):
        opts = {o.flags: o for o in self._r().options}
        self.assertFalse(opts[("-v", "--verbose")].required)

    def test_default_captured(self):
        opts = {o.flags: o for o in self._r().options}
        self.assertEqual(opts[("--port",)].default, "4000")


class Env(unittest.TestCase):
    def _env(self):
        return {e.name: e for e in analyze(SAMPLE, module="cli").env_vars}

    def test_getenv_with_default(self):
        e = self._env()["CODEFORGE_HOST"]
        self.assertTrue(e.has_default)
        self.assertEqual(e.default, "localhost")

    def test_environ_subscript(self):
        self.assertIn("CODEFORGE_DB", self._env())
        self.assertFalse(self._env()["CODEFORGE_DB"].has_default)

    def test_environ_get(self):
        self.assertIn("API_TOKEN", self._env())


class Honesty(unittest.TestCase):
    def test_dynamic_flag_is_unknown(self):
        src = "def f(p, name):\n    p.add_argument(name)\n"
        r = analyze(src)
        self.assertTrue(any("non-literal flag" in u for u in r.unknowns))
        self.assertLess(r.confidence, 1.0)

    def test_click_is_flagged_not_parsed(self):
        src = "import click\n@click.command()\n@click.option('--x')\ndef f(x):\n    pass\n"
        r = analyze(src)
        self.assertTrue(any("not parsed" in u for u in r.unknowns))

    def test_clean_argparse_full_confidence(self):
        self.assertEqual(analyze(SAMPLE).confidence, 1.0)

    def test_no_surface_module(self):
        r = analyze("def f():\n    return 1\n")
        self.assertEqual(r.options, ())
        self.assertEqual(r.env_vars, ())


class RenderAndRefusal(unittest.TestCase):
    def test_render_readable(self):
        out = render(analyze(SAMPLE, module="cli"))
        self.assertIn("subcommands: serve, play", out)
        self.assertIn("CODEFORGE_HOST", out)

    def test_render_empty(self):
        self.assertIn("no CLI or environment surface", render(analyze("x = 1\n")))

    def test_syntax_error_fails_loud(self):
        with self.assertRaises(CliSurfaceError):
            analyze("def bad(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
