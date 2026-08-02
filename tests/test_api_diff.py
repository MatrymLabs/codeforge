"""Test twin for api_diff.py. It classifies public API changes into breaking vs
compatible correctly, catches signature narrowing, stays honest when only a body moved,
and refuses to crash on bad source.

Run:  python3 -m unittest test_api_diff
"""

from __future__ import annotations

import unittest

from kernel.shelf.api_diff import ApiDiffError, diff, render

BASE = """
def keep(a, b):
    return a + b


def gone(x):
    return x


class Service:
    def run(self, job):
        return job

    def _private(self):
        return 1
"""


class Removals(unittest.TestCase):
    def test_removed_function_is_breaking(self):
        new = BASE.replace("def gone(x):\n    return x\n", "")
        report = diff(BASE, new, module="svc")
        self.assertTrue(report.is_breaking)
        self.assertTrue(
            any(c.kind == "removed_symbol" and c.qualname == "gone" for c in report.breaking)
        )

    def test_removed_method_is_breaking(self):
        new = BASE.replace("    def run(self, job):\n        return job\n", "")
        report = diff(BASE, new)
        self.assertTrue(
            any(c.qualname == "Service.run" and c.impact == "breaking" for c in report.breaking)
        )

    def test_private_removal_is_not_reported(self):
        new = BASE.replace("    def _private(self):\n        return 1\n", "")
        report = diff(BASE, new)
        self.assertFalse(report.breaking)  # private members are not the public contract


class Signatures(unittest.TestCase):
    def test_new_required_param_is_breaking(self):
        new = BASE.replace("def keep(a, b):", "def keep(a, b, c):")
        report = diff(BASE, new)
        self.assertTrue(any(c.kind == "added_required_param" for c in report.breaking))

    def test_new_optional_param_is_compatible(self):
        new = BASE.replace("def keep(a, b):", "def keep(a, b, c=0):")
        report = diff(BASE, new)
        self.assertFalse(report.is_breaking)
        self.assertTrue(any(c.kind == "added_optional_param" for c in report.compatible))

    def test_removed_param_is_breaking(self):
        new = BASE.replace("def keep(a, b):", "def keep(a):")
        report = diff(BASE, new)
        self.assertTrue(any(c.kind == "removed_param" for c in report.breaking))

    def test_default_removed_is_breaking(self):
        old = "def f(a, b=1):\n    return a\n"
        new = "def f(a, b):\n    return a\n"
        report = diff(old, new)
        self.assertTrue(any(c.kind == "default_removed" for c in report.breaking))

    def test_lost_kwargs_is_breaking(self):
        old = "def f(a, **kw):\n    return a\n"
        new = "def f(a):\n    return a\n"
        report = diff(old, new)
        self.assertTrue(any(c.kind == "removed_kwargs" for c in report.breaking))


class Additions(unittest.TestCase):
    def test_new_function_is_compatible(self):
        new = BASE + "\ndef added(z):\n    return z\n"
        report = diff(BASE, new)
        self.assertFalse(report.is_breaking)
        self.assertTrue(
            any(c.kind == "added_symbol" and c.qualname == "added" for c in report.compatible)
        )


class Honesty(unittest.TestCase):
    def test_body_change_only_is_unknown_not_safe(self):
        old = "def f(a):\n    return a\n"
        new = "def f(a):\n    return a * 2\n"
        report = diff(old, new)
        self.assertFalse(report.is_breaking)
        self.assertTrue(any(c.kind == "body_changed" for c in report.unknown))
        self.assertLess(report.confidence, 1.0)

    def test_identical_source_no_changes(self):
        report = diff(BASE, BASE)
        self.assertFalse(report.breaking or report.compatible or report.unknown)
        self.assertEqual(report.confidence, 1.0)

    def test_kind_change_is_breaking(self):
        old = "def thing():\n    return 1\n"
        new = "class thing:\n    pass\n"
        report = diff(old, new)
        self.assertTrue(any(c.kind == "kind_changed" for c in report.breaking))


class RenderAndRefusal(unittest.TestCase):
    def test_render_flags_breaking(self):
        new = BASE.replace("def gone(x):\n    return x\n", "")
        self.assertIn("[BREAKING]", render(diff(BASE, new, module="svc")))

    def test_render_clean(self):
        self.assertIn("no public API changes", render(diff(BASE, BASE)))

    def test_syntax_error_fails_loud(self):
        with self.assertRaises(ApiDiffError):
            diff("def ok():\n    pass\n", "def bad(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
