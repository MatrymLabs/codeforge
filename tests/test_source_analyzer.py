"""Test twin for source_analyzer.py. It extracts the right intermediate model from
known source, stays honest about what it cannot resolve (confidence + unknowns),
and never crashes on dynamic code.

Run:  python3 -m unittest test_source_analyzer
"""

from __future__ import annotations

import unittest

from parts.shelf.source_analyzer import AnalyzerError, analyze, render

SAMPLE = '''"""A tiny ledger module.

Longer description ignored.
"""
from __future__ import annotations
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    name: str
    balance: int = 0


class Ledger(Base):
    def post(self, account, amount):
        return amount

    def _private(self):
        return 1


def open_ledger(path):
    return Ledger()
'''


class Identity(unittest.TestCase):
    def test_identity_is_first_docstring_line(self):
        self.assertEqual(analyze(SAMPLE, module="ledger").identity, "A tiny ledger module.")

    def test_no_docstring_is_empty_identity(self):
        self.assertEqual(analyze("x = 1\n").identity, "")


class Extraction(unittest.TestCase):
    def _m(self):
        return analyze(SAMPLE, module="ledger")

    def test_imports(self):
        self.assertEqual(set(self._m().imports), {"json", "dataclasses", "__future__"})

    def test_entity_is_the_dataclass_with_fields(self):
        entities = {e.name: e for e in self._m().entities}
        self.assertIn("Account", entities)
        acct = entities["Account"]
        self.assertTrue(acct.is_dataclass and acct.frozen)
        self.assertEqual([f.name for f in acct.fields], ["name", "balance"])
        self.assertEqual(entities["Account"].fields[0].annotation, "str")

    def test_public_interface_excludes_private(self):
        names = {i.name for i in self._m().interface}
        self.assertIn("open_ledger", names)
        self.assertIn("Ledger", names)
        self.assertNotIn("_private", names)  # private members are not the interface

    def test_function_params_exclude_self(self):
        iface = {i.name: i for i in self._m().interface}
        self.assertEqual(iface["open_ledger"].params, ("path",))

    def test_inheritance_relationship(self):
        self.assertIn(("Ledger", "Base"), self._m().relationships)

    def test_object_base_is_not_a_relationship(self):
        m = analyze("class C(object):\n    pass\n")
        self.assertEqual(m.relationships, ())


class Honesty(unittest.TestCase):
    def test_dynamic_code_lowers_confidence_and_records_unknowns(self):
        m = analyze("def f():\n    exec('x=1')\n")
        self.assertLess(m.confidence, 1.0)
        self.assertTrue(any("exec" in u for u in m.unknowns))

    def test_star_import_is_an_unknown(self):
        m = analyze("from os import *\n")
        self.assertTrue(any("star import" in u for u in m.unknowns))

    def test_clean_module_is_full_confidence(self):
        self.assertEqual(analyze("def f(a, b):\n    return a + b\n").confidence, 1.0)

    def test_confidence_never_below_floor(self):
        src = "\n".join(
            f"def f{i}():\n    exec('x')\n    eval('y')\n    globals()" for i in range(20)
        )
        self.assertGreaterEqual(analyze(src).confidence, 0.3)


class RenderAndRefusal(unittest.TestCase):
    def test_render_is_readable(self):
        out = render(analyze(SAMPLE, module="ledger"))
        self.assertIn("Account", out)
        self.assertIn("identity: A tiny ledger module.", out)

    def test_syntax_error_fails_loud(self):
        with self.assertRaises(AnalyzerError):
            analyze("def oops(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
