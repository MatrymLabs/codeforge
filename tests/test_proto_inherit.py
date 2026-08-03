"""Test twin for proto_inherit.py (RD-2026-0007 Evennia spawner harvest).

Acceptance (single parent, multi-parent left-to-right, child override, nested structural merge, diff
actions, apply_diff), refusal/hostile (unknown parent, cycle, bad parent type, non-dict prototype).
"""

from __future__ import annotations

import unittest

from kernel.shelf import proto_inherit as p


class Flatten(unittest.TestCase):
    def test_no_parent_returns_own_keys(self):
        reg = {"sword": {"name": "sword", "damage": 5}}
        self.assertEqual(p.flatten("sword", reg), {"name": "sword", "damage": 5})

    def test_single_parent_is_inherited(self):
        reg = {
            "weapon": {"damage": 3, "slot": "hand"},
            "sword": {"parent": "weapon", "name": "sword"},
        }
        self.assertEqual(p.flatten("sword", reg), {"damage": 3, "slot": "hand", "name": "sword"})

    def test_child_overrides_parent(self):
        reg = {"weapon": {"damage": 3}, "sword": {"parent": "weapon", "damage": 9}}
        self.assertEqual(p.flatten("sword", reg)["damage"], 9)

    def test_multi_parent_left_to_right_later_wins(self):
        reg = {
            "sharp": {"damage": 3},
            "heavy": {"damage": 7, "weight": 10},
            "greatsword": {"parent": ["sharp", "heavy"]},
        }
        # heavy is later so its damage wins; weight comes along
        self.assertEqual(p.flatten("greatsword", reg), {"damage": 7, "weight": 10})

    def test_nested_dicts_merge_structurally(self):
        reg = {
            "base": {"attrs": {"str": 1, "dex": 1}},
            "hero": {"parent": "base", "attrs": {"dex": 5, "wis": 3}},
        }
        self.assertEqual(p.flatten("hero", reg)["attrs"], {"str": 1, "dex": 5, "wis": 3})

    def test_deep_chain(self):
        reg = {
            "a": {"x": 1},
            "b": {"parent": "a", "y": 2},
            "c": {"parent": "b", "z": 3},
        }
        self.assertEqual(p.flatten("c", reg), {"x": 1, "y": 2, "z": 3})

    def test_parent_key_is_dropped_from_result(self):
        reg = {"w": {"d": 1}, "s": {"parent": "w"}}
        self.assertNotIn("parent", p.flatten("s", reg))


class Diff(unittest.TestCase):
    def test_add_update_remove_keep(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 20, "d": 4}
        plan = p.diff(old, new)
        self.assertEqual(plan["a"], (p.KEEP, 1))
        self.assertEqual(plan["b"], (p.UPDATE, 20))
        self.assertEqual(plan["c"], (p.REMOVE, 3))
        self.assertEqual(plan["d"], (p.ADD, 4))

    def test_apply_diff_pushes_changes_copy_on_write(self):
        inst = {"a": 1, "b": 2, "c": 3, "own": "keep_me"}
        plan = p.diff({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 20, "d": 4})
        out = p.apply_diff(inst, plan)
        self.assertEqual(out["b"], 20)  # updated
        self.assertNotIn("c", out)  # removed
        self.assertEqual(out["d"], 4)  # added
        self.assertEqual(out["own"], "keep_me")  # instance-only field survives
        self.assertEqual(inst["b"], 2)  # original untouched (copy-on-write)


class Refusal(unittest.TestCase):
    def test_unknown_prototype_fails_loud(self):
        with self.assertRaises(p.PrototypeError):
            p.flatten("ghost", {"sword": {"d": 1}})

    def test_unknown_parent_fails_loud(self):
        with self.assertRaises(p.PrototypeError):
            p.flatten("sword", {"sword": {"parent": "missing"}})

    def test_parent_cycle_fails_loud(self):
        reg = {"a": {"parent": "b"}, "b": {"parent": "a"}}
        with self.assertRaises(p.PrototypeError):
            p.flatten("a", reg)

    def test_bad_parent_type_fails_loud(self):
        with self.assertRaises(p.PrototypeError):
            p.flatten("s", {"s": {"parent": 42}})

    def test_non_dict_prototype_fails_loud(self):
        with self.assertRaises(p.PrototypeError):
            p.flatten("s", {"s": ["not", "a", "dict"]})


if __name__ == "__main__":
    unittest.main()
