"""The Debugging Lab, exercised end-to-end - the real consumer.

CodeForge is a self-auditing engineering stack, so its own Debugging Lab shelf must run
its three honest, deterministic pointers on real inputs: SBFL localizes a fault from a
coverage spectrum, ddmin shrinks a failing input to its 1-minimal reproducer, and
profile_hotspots ranks where time went in a real profiled call. Each keeps its honesty
caveat.
"""

from __future__ import annotations

from kernel.shelf import ddmin, profile_hotspots, sbfl


def test_sbfl_localizes_the_planted_fault() -> None:
    # two failing tests both hit "buggy"; passing tests mostly do not
    coverage = {
        "t1": {"setup", "buggy"},
        "t2": {"setup", "buggy"},
        "t3": {"setup", "safe"},
        "t4": {"setup", "safe"},
    }
    outcomes = {"t1": False, "t2": False, "t3": True, "t4": True}
    report = sbfl.localize(coverage, outcomes, formula="ochiai")
    assert report.prime_suspects == ("buggy",)
    assert "ICSE 2017" in report.caveat  # honesty rides along


def test_ddmin_shrinks_to_the_minimal_reproducer() -> None:
    seq = list(range(1, 41))

    def still_fails(subset: list[int]) -> bool:
        return 9 in subset and 27 in subset

    reduction = ddmin.ddmin(seq, still_fails)
    assert set(reduction.minimal) == {9, 27}
    assert reduction.is_one_minimal
    assert reduction.reduced_size < reduction.original_size  # a smaller failing case


def test_profile_hotspots_finds_the_busy_function() -> None:
    def busy() -> int:
        total = 0
        for i in range(150_000):
            total += i % 7
        return total

    def driver() -> None:
        busy()

    report = profile_hotspots.profile_call(driver, top=8)
    assert any("busy" in h.function for h in report.hotspots)
    assert "benchmark" in report.caveat  # the gate caveat rides along


def test_the_lab_composes_localize_then_shrink() -> None:
    # SBFL points at a suspect element; ddmin confirms the minimal failing set around it
    coverage = {"f1": {"a", "x"}, "f2": {"b", "x"}, "p1": {"a", "b"}}
    outcomes = {"f1": False, "f2": False, "p1": True}
    suspect = sbfl.localize(coverage, outcomes).prime_suspects[0]
    assert suspect == "x"  # x is in both failures, nothing else is

    reduction = ddmin.ddmin(["a", "x", "b", "c"], lambda s: "x" in s)
    assert list(reduction.minimal) == ["x"]
