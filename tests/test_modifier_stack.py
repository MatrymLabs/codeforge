"""Test twin for modifier_stack.py (RD-2026-0007 Evennia buff-handler keystone harvest).

Acceptance (add fold, mult fold, combined order (base+add)*mult, stacking, conditional gating,
source removal, breakdown provenance), canonical-state (resolve never mutates; add/remove copy-on-
write), and refusal/hostile (bad op, zero/negative stacks, blank stat/source fail loud).
"""

from __future__ import annotations

import unittest

from kernel.shelf import modifier_stack as m


class Fold(unittest.TestCase):
    def test_no_mods_returns_base(self):
        self.assertEqual(m.resolve(10.0, m.Stack(), "attack"), 10.0)

    def test_additive_mods_sum(self):
        s = m.Stack().add(m.Mod("attack", m.ADD, 3)).add(m.Mod("attack", m.ADD, 2))
        self.assertEqual(m.resolve(10.0, s, "attack"), 15.0)

    def test_multiplicative_mods_multiply(self):
        s = m.Stack().add(m.Mod("attack", m.MULT, 1.5)).add(m.Mod("attack", m.MULT, 2.0))
        self.assertEqual(m.resolve(10.0, s, "attack"), 30.0)

    def test_order_is_base_plus_add_times_mult(self):
        s = m.Stack().add(m.Mod("attack", m.ADD, 5)).add(m.Mod("attack", m.MULT, 2.0))
        self.assertEqual(m.resolve(10.0, s, "attack"), 30.0)  # (10+5)*2, not 10 + 5*2

    def test_only_matching_stat_contributes(self):
        s = m.Stack().add(m.Mod("attack", m.ADD, 5)).add(m.Mod("defense", m.ADD, 99))
        self.assertEqual(m.resolve(10.0, s, "attack"), 15.0)

    def test_stacks_scale_add_and_mult(self):
        add = m.Mod("attack", m.ADD, 2, stacks=3)  # +6
        mult = m.Mod("attack", m.MULT, 2.0, stacks=2)  # *4
        self.assertEqual(m.resolve(10.0, m.Stack().add(add).add(mult), "attack"), 64.0)  # (10+6)*4

    def test_negative_add_is_a_debuff(self):
        s = m.Stack().add(m.Mod("attack", m.ADD, -4))
        self.assertEqual(m.resolve(10.0, s, "attack"), 6.0)


class Conditional(unittest.TestCase):
    def test_condition_gates_the_mod(self):
        low_hp = m.Mod("attack", m.ADD, 10, condition=lambda c: c["hp"] < 5)
        s = m.Stack().add(low_hp)
        self.assertEqual(m.resolve(10.0, s, "attack", ctx={"hp": 3}), 20.0)  # enraged
        self.assertEqual(m.resolve(10.0, s, "attack", ctx={"hp": 9}), 10.0)  # dormant


class Sources(unittest.TestCase):
    def test_remove_by_source_drops_only_that_source(self):
        s = (
            m.Stack()
            .add(m.Mod("attack", m.ADD, 5, source="rusty_sword"))
            .add(m.Mod("attack", m.ADD, 3, source="blessing"))
        )
        after = s.remove_by_source("rusty_sword")
        self.assertEqual(m.resolve(10.0, after, "attack"), 13.0)  # only the blessing remains

    def test_remove_unknown_source_is_noop(self):
        s = m.Stack().add(m.Mod("attack", m.ADD, 5, source="rusty_sword"))
        self.assertIs(s.remove_by_source("nope"), s)

    def test_sources_lists_distinct_in_order(self):
        s = (
            m.Stack()
            .add(m.Mod("attack", m.ADD, 1, source="a"))
            .add(m.Mod("attack", m.ADD, 1, source="b"))
            .add(m.Mod("defense", m.ADD, 1, source="a"))
        )
        self.assertEqual(s.sources(), ("a", "b"))

    def test_explain_names_contributions(self):
        s = (
            m.Stack()
            .add(m.Mod("attack", m.ADD, 5, source="sword"))
            .add(m.Mod("attack", m.MULT, 2.0, source="rage"))
        )
        b = m.explain(10.0, s, "attack")
        self.assertEqual(b.final, 30.0)
        self.assertEqual(b.additive, 5.0)
        self.assertEqual(b.multiplier, 2.0)
        self.assertIn(("sword", 5.0), b.contributions)
        self.assertIn(("rage", 2.0), b.contributions)


class CanonicalState(unittest.TestCase):
    def test_resolve_does_not_mutate(self):
        s = m.Stack().add(m.Mod("attack", m.ADD, 5))
        m.resolve(10.0, s, "attack")
        self.assertEqual(len(s.mods), 1)  # unchanged

    def test_add_is_copy_on_write(self):
        base = m.Stack()
        derived = base.add(m.Mod("attack", m.ADD, 5))
        self.assertEqual(base.mods, ())  # original untouched
        self.assertEqual(len(derived.mods), 1)


class Refusal(unittest.TestCase):
    def test_bad_op_fails_loud(self):
        with self.assertRaises(m.ModifierError):
            m.Mod("attack", "divide", 2)

    def test_non_positive_stacks_fail_loud(self):
        with self.assertRaises(m.ModifierError):
            m.Mod("attack", m.ADD, 2, stacks=0)

    def test_blank_stat_fails_loud(self):
        with self.assertRaises(m.ModifierError):
            m.Mod("", m.ADD, 2)
        with self.assertRaises(m.ModifierError):
            m.resolve(10.0, m.Stack(), "  ")

    def test_blank_source_removal_fails_loud(self):
        with self.assertRaises(m.ModifierError):
            m.Stack().remove_by_source("")


if __name__ == "__main__":
    unittest.main()
