"""Test twin for checklist_gate.py. The property: a required item that is unattested
or false BLOCKS the action and names itself; optional items may be absent.

Run:  python3 -m unittest test_checklist_gate
"""

from __future__ import annotations

import unittest

from kernel.shelf.checklist_gate import (
    Checklist,
    ChecklistError,
    GateBlocked,
    Item,
    missing,
    time_out,
)


def _all_true(checklist: Checklist) -> dict:
    return {i.key: True for i in checklist.items}


class Verify(unittest.TestCase):
    def test_fully_attested_passes(self):
        c = time_out()
        checklist_gate_ok = verify_ok(c, _all_true(c))
        self.assertTrue(checklist_gate_ok)

    def test_missing_required_blocks_and_names_it(self):
        c = time_out()
        att = _all_true(c)
        del att["rollback_plan"]
        with self.assertRaises(GateBlocked) as ctx:
            from kernel.shelf.checklist_gate import verify

            verify(c, att)
        self.assertIn("rollback_plan", ctx.exception.failures)
        self.assertEqual(ctx.exception.phase, "time-out")

    def test_false_attestation_blocks(self):
        from kernel.shelf.checklist_gate import verify

        c = time_out()
        att = _all_true(c)
        att["authorized"] = False
        with self.assertRaises(GateBlocked):
            verify(c, att)

    def test_optional_item_may_be_absent(self):
        from kernel.shelf.checklist_gate import verify

        c = time_out()
        att = {i.key: True for i in c.items if i.required}  # omit the optional one
        verify(c, att)  # no raise

    def test_missing_lists_the_gaps(self):
        c = time_out()
        self.assertIn("repo_context", missing(c, {}))
        self.assertEqual(missing(c, _all_true(c)), ())

    def test_unknown_attestation_key_ignored(self):
        from kernel.shelf.checklist_gate import verify

        c = Checklist("sign-in", (Item("x", "confirm x"),))
        verify(c, {"x": True, "irrelevant": False})  # no raise


class Refusal(unittest.TestCase):
    def test_empty_phase(self):
        with self.assertRaises(ChecklistError):
            Checklist("", (Item("x", "p"),))

    def test_no_items(self):
        with self.assertRaises(ChecklistError):
            Checklist("time-out", ())

    def test_duplicate_keys(self):
        with self.assertRaises(ChecklistError):
            Checklist("t", (Item("x", "a"), Item("x", "b")))

    def test_empty_item_key(self):
        with self.assertRaises(ChecklistError):
            Item("", "prompt")

    def test_non_mapping_attestations(self):
        from kernel.shelf.checklist_gate import verify

        with self.assertRaises(ChecklistError):
            verify(time_out(), ["not", "a", "map"])


def verify_ok(checklist, attestations) -> bool:
    from kernel.shelf.checklist_gate import verify

    try:
        verify(checklist, attestations)
        return True  # noqa: TRY300
    except GateBlocked:
        return False


if __name__ == "__main__":
    unittest.main()
