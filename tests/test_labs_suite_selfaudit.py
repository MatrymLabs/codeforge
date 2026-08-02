"""The Synthesis + Governance + AI/Orchestration Labs, exercised on CodeForge itself.

CodeForge is a self-auditing engineering stack, so this suite of shelf parts must run on
its own code: content_address finds structural clones, file_plan grades the repo's
structure, hotspots ranks its churn x complexity debt, and a behavior_tree drives a small
decision policy. Each keeps its honesty contract.
"""

from __future__ import annotations

import pathlib

from kernel.shelf import behavior_tree as bt
from kernel.shelf import content_address, file_plan, hotspots

_SHELF = pathlib.Path(__file__).resolve().parent.parent / "parts" / "shelf"


def test_content_address_finds_a_clone_group() -> None:
    store = content_address.Store(normalize_locals=True)
    # two structurally-identical functions with different local names -> one address
    store.add("f_count", "def f(count):\n    total = count + 1\n    return total\n")
    store.add("f_n", "def g(n):\n    result = n + 1\n    return result\n")
    assert store.unique_count() == 1
    assert store.clones()


def test_file_plan_grades_the_shelf_repo() -> None:
    root = _SHELF.parent.parent  # the codeforge repo root
    report = file_plan.check(file_plan.scan(root))
    # codeforge carries the canonical files, so it passes with a strong score
    assert report.passed
    assert report.score >= 0.9


def test_hotspots_ranks_by_churn_times_complexity() -> None:
    churn = {"hot.py": 40, "stable.py": 1, "simple.py": 50}
    complexity = {"hot.py": 30, "stable.py": 35, "simple.py": 2}
    report = hotspots.rank(churn, complexity)
    assert report.prime_hotspot == "hot.py"  # only the churny-AND-complex file leads
    assert "PRIORITIZATION" in report.caveat


def test_behavior_tree_drives_a_decision_policy() -> None:
    tree = bt.Selector(
        children=(
            bt.Sequence(
                children=(
                    bt.Condition(pred=lambda c: c["ready"]),
                    bt.Action(fn=lambda c: (c["log"].append("go"), bt.Status.SUCCESS)[1]),
                )
            ),
            bt.Action(fn=lambda c: (c["log"].append("wait"), bt.Status.SUCCESS)[1]),
        )
    )
    ready = {"ready": True, "log": []}
    tree.tick(ready)
    assert ready["log"] == ["go"]
    waiting = {"ready": False, "log": []}
    tree.tick(waiting)
    assert waiting["log"] == ["wait"]
