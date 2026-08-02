"""Test twin for context_selector.py. The property: the highest-value items that fit
the budget are chosen, deterministically, and an over-cost item never blocks a
cheaper later one.

Run:  python3 -m unittest test_context_selector
"""

from __future__ import annotations

import unittest

from kernel.shelf.context_selector import ContextError, Item, Selection, score, select

WEIGHTS = {"name_match": 2.0, "centrality": 1.0, "recency": 0.5}


def item(id_: str, cost: int = 1, **signals) -> Item:
    return Item(id_, signals, cost)


class Scoring(unittest.TestCase):
    def test_weighted_sum(self):
        it = item("a", name_match=1.0, centrality=0.5)
        self.assertEqual(score(it, WEIGHTS), 2.0 * 1.0 + 1.0 * 0.5)

    def test_unknown_signal_is_zero(self):
        self.assertEqual(score(item("a", other=9.0), WEIGHTS), 0.0)


class Select(unittest.TestCase):
    def test_picks_highest_scoring_within_item_budget(self):
        items = [item("hi", name_match=1.0), item("mid", centrality=1.0), item("lo", recency=1.0)]
        sel = select(items, WEIGHTS, max_items=2)
        self.assertEqual([i.id for i in sel.items], ["hi", "mid"])
        self.assertIn("lo", sel.dropped)
        self.assertEqual(sel.considered, 3)

    def test_cost_budget(self):
        items = [
            item("a", cost=3, name_match=1.0),
            item("b", cost=2, centrality=1.0),
            item("c", cost=2, recency=1.0),
        ]
        sel = select(items, WEIGHTS, max_cost=5)  # a(3) + b(2) = 5, c drops
        self.assertEqual([i.id for i in sel.items], ["a", "b"])
        self.assertEqual(sel.total_cost, 5)

    def test_overcost_item_does_not_block_cheaper_one(self):
        items = [item("huge", cost=100, name_match=1.0), item("small", cost=1, centrality=1.0)]
        sel = select(items, WEIGHTS, max_cost=5)
        self.assertEqual([i.id for i in sel.items], ["small"])  # huge skipped, small still chosen
        self.assertIn("huge", sel.dropped)

    def test_deterministic_tiebreak_by_id(self):
        items = [item("b", name_match=1.0), item("a", name_match=1.0)]
        sel = select(items, WEIGHTS, max_items=1)
        self.assertEqual([i.id for i in sel.items], ["a"])  # equal score -> id order

    def test_both_budgets_apply(self):
        items = [item(str(i), cost=1, name_match=1.0) for i in range(10)]
        sel = select(items, WEIGHTS, max_items=3, max_cost=100)
        self.assertEqual(len(sel.items), 3)

    def test_all_fit(self):
        items = [item("a", name_match=1.0), item("b", centrality=1.0)]
        sel = select(items, WEIGHTS, max_items=10)
        self.assertEqual(len(sel.items), 2)
        self.assertEqual(sel.dropped, ())
        self.assertIsInstance(sel, Selection)


class Refusal(unittest.TestCase):
    def test_no_budget(self):
        with self.assertRaises(ContextError):
            select([item("a", name_match=1.0)], WEIGHTS)

    def test_empty_weights(self):
        with self.assertRaises(ContextError):
            select([item("a")], {}, max_items=1)

    def test_bad_budgets(self):
        with self.assertRaises(ContextError):
            select([item("a")], WEIGHTS, max_items=0)
        with self.assertRaises(ContextError):
            select([item("a")], WEIGHTS, max_cost=0)

    def test_bad_item(self):
        with self.assertRaises(ContextError):
            Item("", {})
        with self.assertRaises(ContextError):
            Item("a", {}, cost=0)


if __name__ == "__main__":
    unittest.main()
