"""Test twin for model_extractor.py. It finds entity relationships (reference,
collection, optional, inheritance), infers state machines from enums + observed member
assignments, flags unreached states, stays honest about dynamic state, and refuses to
crash on bad source.

Run:  python3 -m unittest test_model_extractor
"""

from __future__ import annotations

import unittest

from parts.shelf.model_extractor import ModelExtractorError, analyze, render

SAMPLE = """
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Address:
    city: str


@dataclass
class Customer:
    name: str
    address: Address
    aliases: list[str]


@dataclass
class Order:
    customer: Customer
    lines: list[Address]
    coupon: Address | None
    status: Status

    def open(self):
        self.status = Status.OPEN

    def close(self):
        self.status = Status.CLOSED
"""


class Entities(unittest.TestCase):
    def _r(self):
        return analyze(SAMPLE, module="shop")

    def test_entities_found(self):
        self.assertEqual(set(self._r().entities), {"Address", "Customer", "Order"})

    def test_enum_is_not_an_entity(self):
        self.assertNotIn("Status", self._r().entities)


class Relationships(unittest.TestCase):
    def _rels(self):
        return {(r.source, r.target, r.kind) for r in analyze(SAMPLE, module="shop").relationships}

    def test_direct_reference(self):
        self.assertIn(("Customer", "Address", "reference"), self._rels())

    def test_collection_reference(self):
        self.assertIn(("Order", "Address", "collection"), self._rels())

    def test_optional_reference(self):
        self.assertIn(("Order", "Address", "optional"), self._rels())

    def test_scalar_field_is_not_a_relationship(self):
        # `name: str` and `aliases: list[str]` must not create edges (str is not an entity)
        targets = {r.target for r in analyze(SAMPLE, module="shop").relationships}
        self.assertNotIn("str", targets)

    def test_inheritance_edge(self):
        src = (
            "from dataclasses import dataclass\n@dataclass\nclass A:\n    x: int\n"
            "class B(A):\n    y: int\n"
        )
        rels = {(r.source, r.target, r.kind) for r in analyze(src).relationships}
        self.assertIn(("B", "A", "inheritance"), rels)


class StateMachines(unittest.TestCase):
    def _sm(self):
        machines = {m.enum: m for m in analyze(SAMPLE, module="shop").state_machines}
        return machines["Status"]

    def test_states_are_the_enum_members(self):
        self.assertEqual(self._sm().states, ("DRAFT", "OPEN", "CLOSED"))

    def test_transitions_labelled_by_setter(self):
        trans = {(t.setter, t.to_state) for t in self._sm().transitions}
        self.assertIn(("open", "OPEN"), trans)
        self.assertIn(("close", "CLOSED"), trans)

    def test_unreached_state_is_reported(self):
        # DRAFT is declared but never assigned in the module
        self.assertIn("DRAFT", self._sm().unreached)


class Honesty(unittest.TestCase):
    def test_setattr_lowers_confidence(self):
        src = "class S:\n    def f(self, v):\n        setattr(self, 'status', v)\n"
        r = analyze(src)
        self.assertLess(r.confidence, 1.0)
        self.assertTrue(any("setattr" in u for u in r.unknowns))

    def test_clean_module_full_confidence(self):
        self.assertEqual(analyze(SAMPLE).confidence, 1.0)

    def test_module_with_no_model_is_empty_not_error(self):
        r = analyze("def f():\n    return 1\n")
        self.assertEqual(r.entities, ())
        self.assertEqual(r.state_machines, ())


class RenderAndRefusal(unittest.TestCase):
    def test_render_readable(self):
        out = render(analyze(SAMPLE, module="shop"))
        self.assertIn("Order", out)
        self.assertIn("state machine Status", out)
        self.assertIn("-> OPEN", out)

    def test_syntax_error_fails_loud(self):
        with self.assertRaises(ModelExtractorError):
            analyze("class Broken(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
