"""Test twin for behavior_tree.py. Sequence is AND, Selector is OR, RUNNING propagates,
decorators flip/repeat, Parallel honours its threshold, a guard NPC tree picks the right
branch reactively, run() settles or caps, and bad actions are refused.

Run:  python3 -m unittest test_behavior_tree
"""

from __future__ import annotations

import unittest

from kernel.shelf.behavior_tree import (
    Action,
    AlwaysFail,
    BehaviorTreeError,
    Condition,
    Inverter,
    Parallel,
    Repeater,
    RunResult,
    Selector,
    Sequence,
    Status,
    run,
)


def _leaf(status: Status) -> Action:
    return Action(fn=lambda _c: status)


class SequenceSelector(unittest.TestCase):
    def test_sequence_all_success(self):
        seq = Sequence(children=(_leaf(Status.SUCCESS), _leaf(Status.SUCCESS)))
        self.assertIs(seq.tick(None), Status.SUCCESS)

    def test_sequence_fails_on_first_failure(self):
        calls = []
        a = Action(fn=lambda _c: (calls.append("a"), Status.FAILURE)[1])
        b = Action(fn=lambda _c: (calls.append("b"), Status.SUCCESS)[1])
        seq = Sequence(children=(a, b))
        self.assertIs(seq.tick(None), Status.FAILURE)
        self.assertEqual(calls, ["a"])  # short-circuits: b never runs

    def test_sequence_running_propagates(self):
        seq = Sequence(
            children=(_leaf(Status.SUCCESS), _leaf(Status.RUNNING), _leaf(Status.SUCCESS))
        )
        self.assertIs(seq.tick(None), Status.RUNNING)

    def test_empty_sequence_is_success(self):
        self.assertIs(Sequence(children=()).tick(None), Status.SUCCESS)

    def test_selector_first_success_wins(self):
        calls = []
        a = Action(fn=lambda _c: (calls.append("a"), Status.FAILURE)[1])
        b = Action(fn=lambda _c: (calls.append("b"), Status.SUCCESS)[1])
        c = Action(fn=lambda _c: (calls.append("c"), Status.SUCCESS)[1])
        self.assertIs(Selector(children=(a, b, c)).tick(None), Status.SUCCESS)
        self.assertEqual(calls, ["a", "b"])  # c never runs

    def test_selector_all_fail_is_failure(self):
        self.assertIs(
            Selector(children=(_leaf(Status.FAILURE), _leaf(Status.FAILURE))).tick(None),
            Status.FAILURE,
        )

    def test_empty_selector_is_failure(self):
        self.assertIs(Selector(children=()).tick(None), Status.FAILURE)


class Decorators(unittest.TestCase):
    def test_inverter_flips(self):
        self.assertIs(Inverter(child=_leaf(Status.SUCCESS)).tick(None), Status.FAILURE)
        self.assertIs(Inverter(child=_leaf(Status.FAILURE)).tick(None), Status.SUCCESS)
        self.assertIs(Inverter(child=_leaf(Status.RUNNING)).tick(None), Status.RUNNING)

    def test_always_fail(self):
        self.assertIs(AlwaysFail(child=_leaf(Status.SUCCESS)).tick(None), Status.FAILURE)

    def test_repeater_runs_n_times(self):
        n = {"count": 0}

        def bump(_c: object) -> Status:
            n["count"] += 1
            return Status.SUCCESS

        self.assertIs(Repeater(child=Action(fn=bump), times=3).tick(None), Status.SUCCESS)
        self.assertEqual(n["count"], 3)

    def test_repeater_stops_on_failure(self):
        n = {"count": 0}

        def bump(_c: object) -> Status:
            n["count"] += 1
            return Status.FAILURE

        Repeater(child=Action(fn=bump), times=5).tick(None)
        self.assertEqual(n["count"], 1)  # stopped after the first failure


class ParallelNode(unittest.TestCase):
    def test_threshold_met(self):
        p = Parallel(
            children=(_leaf(Status.SUCCESS), _leaf(Status.SUCCESS), _leaf(Status.FAILURE)),
            threshold=2,
        )
        self.assertIs(p.tick(None), Status.SUCCESS)

    def test_threshold_impossible_is_failure(self):
        p = Parallel(
            children=(_leaf(Status.FAILURE), _leaf(Status.FAILURE), _leaf(Status.SUCCESS)),
            threshold=2,
        )
        self.assertIs(p.tick(None), Status.FAILURE)  # only 1 can succeed, need 2

    def test_still_possible_is_running(self):
        p = Parallel(
            children=(_leaf(Status.SUCCESS), _leaf(Status.RUNNING), _leaf(Status.RUNNING)),
            threshold=2,
        )
        self.assertIs(p.tick(None), Status.RUNNING)

    def test_bad_threshold_refused(self):
        with self.assertRaises(BehaviorTreeError):
            Parallel(children=(_leaf(Status.SUCCESS),), threshold=0)


class GuardNpcReactive(unittest.TestCase):
    """A classic guard NPC: attack if an enemy is visible, else patrol, else idle."""

    def _tree(self) -> Selector:
        return Selector(
            name="guard-brain",
            children=(
                Sequence(
                    children=(
                        Condition(name="enemy?", pred=lambda c: c["enemy_visible"]),
                        Action(
                            name="attack",
                            fn=lambda c: (c.setdefault("log", []).append("attack"), Status.SUCCESS)[
                                1
                            ],
                        ),
                    )
                ),
                Sequence(
                    children=(
                        Condition(name="waypoint?", pred=lambda c: c["has_waypoint"]),
                        Action(
                            name="patrol",
                            fn=lambda c: (c["log"].append("patrol"), Status.SUCCESS)[1],
                        ),
                    )
                ),
                Action(name="idle", fn=lambda c: (c["log"].append("idle"), Status.SUCCESS)[1]),
            ),
        )

    def test_attacks_when_enemy_visible(self):
        ctx = {"enemy_visible": True, "has_waypoint": True, "log": []}
        self.assertIs(self._tree().tick(ctx), Status.SUCCESS)
        self.assertEqual(ctx["log"], ["attack"])  # higher-priority branch pre-empts patrol

    def test_patrols_when_no_enemy_but_has_waypoint(self):
        ctx = {"enemy_visible": False, "has_waypoint": True, "log": []}
        self._tree().tick(ctx)
        self.assertEqual(ctx["log"], ["patrol"])

    def test_idles_as_last_resort(self):
        ctx = {"enemy_visible": False, "has_waypoint": False, "log": []}
        self._tree().tick(ctx)
        self.assertEqual(ctx["log"], ["idle"])


class RunAndRefusal(unittest.TestCase):
    def test_run_settles(self):
        result = run(_leaf(Status.SUCCESS), None)
        self.assertIsInstance(result, RunResult)
        self.assertIs(result.status, Status.SUCCESS)
        self.assertEqual(result.ticks, 1)

    def test_run_caps_an_always_running_tree(self):
        result = run(_leaf(Status.RUNNING), None, max_ticks=5)
        self.assertTrue(result.capped)
        self.assertEqual(result.ticks, 5)
        self.assertTrue(result.notes)

    def test_action_returning_bool_maps_to_status(self):
        self.assertIs(Action(fn=lambda _c: True).tick(None), Status.SUCCESS)
        self.assertIs(Action(fn=lambda _c: False).tick(None), Status.FAILURE)

    def test_bad_action_return_refused(self):
        with self.assertRaises(BehaviorTreeError):
            Action(fn=lambda _c: "nope").tick(None)

    def test_bad_max_ticks_refused(self):
        with self.assertRaises(BehaviorTreeError):
            run(_leaf(Status.SUCCESS), None, max_ticks=0)


if __name__ == "__main__":
    unittest.main()
