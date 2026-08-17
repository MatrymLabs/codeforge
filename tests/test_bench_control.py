"""Test twin for kernel/bench_control.py.

The load-bearing promise: the runner controls the machine (pins a quiet core, seeds a repeatable
interleave) AND stays honest about what it actually achieved - a scheduler that refuses the pin is
a reported condition, not a crash. Every OS call is an injected seam, so the whole suite runs on a
SIMULATED machine with no real second core. Covers acceptance (pin + verdict), refusal (impossible
cores fail loud), honesty (EPERM -> pinned=False, not raised), and determinism (seeded interleave +
affinity always restored). Hostile cases included: an off-limits core, a lying getter, EPERM.
"""

from __future__ import annotations

import unittest
from collections.abc import Callable

from kernel import bench_control as bc
from kernel import bench_protocol as bp


class FakeMachine:
    """A scriptable stand-in for the three OS affinity calls: a fixed core count, the mask the
    process currently holds, and an optional set of cores the scheduler will REFUSE to pin to."""

    def __init__(self, cores: int, *, mask: set[int] | None = None, refuse: set[int] | None = None):
        self.cores = cores
        self.mask = set(mask if mask is not None else range(cores))
        self.refuse = refuse or set()
        self.set_calls: list[set[int]] = []

    def setter(self, pid: int, mask: set[int]) -> None:
        self.set_calls.append(set(mask))
        if mask & self.refuse:
            raise PermissionError("Operation not permitted")  # an OSError subclass, like real EPERM  # noqa: E501, TRY003
        self.mask = set(mask)

    def getter(self, pid: int) -> set[int]:
        return set(self.mask)

    def ncpu(self) -> int:
        return self.cores


class _Clock:
    """A deterministic clock the WORKLOAD advances, so an injected timer sees a real difference
    with no wall clock: `read` returns the current time; `costing(d)` returns a fn that, when run
    between two `read`s, makes that measured interval exactly `d`. A baseline that costs 5 and a
    candidate that costs 1 therefore produce Cliff's delta = 1.0 (candidate strictly faster)."""

    def __init__(self) -> None:
        self.now = 0.0

    def read(self) -> float:
        return self.now

    def costing(self, d: float) -> Callable[[], None]:
        def _run() -> None:
            self.now += d

        return _run


class QuietCore(unittest.TestCase):
    def test_picks_highest_available_core(self):
        m = FakeMachine(4)
        # no isolated cores -> highest-numbered available (core 0 fields interrupts, worst choice)
        self.assertEqual(bc.quiet_core(getter=m.getter, ncpu=m.ncpu, isolated_path=_missing()), 3)

    def test_prefers_a_usable_isolated_core(
        self,
    ):
        m = FakeMachine(4)
        path = _TmpText("2-3")  # kernel isolated cores 2,3
        self.assertEqual(bc.quiet_core(getter=m.getter, ncpu=m.ncpu, isolated_path=path), 3)

    def test_ignores_isolated_core_we_cannot_run_on(self):
        m = FakeMachine(4, mask={0, 1})  # allowed only on 0,1
        path = _TmpText("3")  # isolated core 3 is off-limits to us
        # falls back to the highest AVAILABLE core, not the off-limits isolated one
        self.assertEqual(bc.quiet_core(getter=m.getter, ncpu=m.ncpu, isolated_path=path), 1)

    def test_empty_mask_fails_loud(self):
        m = FakeMachine(4, mask=set())
        with self.assertRaises(bc.BenchControlError):
            bc.quiet_core(getter=m.getter, ncpu=m.ncpu, isolated_path=_missing())


class PinProcess(unittest.TestCase):
    def test_successful_pin_reports_pinned(self):
        m = FakeMachine(4)
        rep = bc.pin_process(3, setter=m.setter, getter=m.getter, ncpu=m.ncpu)
        self.assertTrue(rep.pinned)
        self.assertEqual(rep.achieved_affinity, (3,))
        self.assertEqual(rep.requested_core, 3)
        self.assertIn("pinned to core 3", rep.note)

    def test_core_out_of_range_fails_loud(self):
        m = FakeMachine(4)
        with self.assertRaises(bc.BenchControlError):
            bc.pin_process(4, setter=m.setter, getter=m.getter, ncpu=m.ncpu)  # cores are 0..3

    def test_negative_core_fails_loud(self):
        m = FakeMachine(4)
        with self.assertRaises(bc.BenchControlError):
            bc.pin_process(-1, setter=m.setter, getter=m.getter, ncpu=m.ncpu)

    def test_refused_pin_is_a_condition_not_a_crash(self):
        # a scheduler that refuses core 3 (cpuset/cgroup) -> honest pinned=False, no exception
        m = FakeMachine(4, refuse={3})
        rep = bc.pin_process(3, setter=m.setter, getter=m.getter, ncpu=m.ncpu)
        self.assertFalse(rep.pinned)
        self.assertIn("refused", rep.note)

    def test_partial_pin_is_reported(self):
        # setter 'succeeds' but the mask never narrows to exactly {3} (a lying/coarse OS)
        class Sticky(FakeMachine):
            def setter(self, pid: int, mask: set[int]) -> None:
                pass  # accept, but do not change the mask

        m = Sticky(4)  # mask stays {0,1,2,3}
        rep = bc.pin_process(3, setter=m.setter, getter=m.getter, ncpu=m.ncpu)
        self.assertFalse(rep.pinned)
        self.assertIn("not exclusively pinned", rep.note)

    def test_bad_cpu_count_fails_loud(self):
        m = FakeMachine(4)
        with self.assertRaises(bc.BenchControlError):
            bc.pin_process(0, setter=m.setter, getter=m.getter, ncpu=lambda: None)


class Interleave(unittest.TestCase):
    def test_balanced_and_seed_reproducible(self):
        a = bc.build_interleave(30, 3, seed=7)
        b = bc.build_interleave(30, 3, seed=7)
        self.assertEqual(a, b)  # same seed -> same schedule (repeatable evidence)
        self.assertEqual(a.count("b"), 33)  # warmup+repeats each
        self.assertEqual(a.count("c"), 33)

    def test_different_seed_differs(self):
        self.assertNotEqual(bc.build_interleave(30, 3, seed=1), bc.build_interleave(30, 3, seed=2))

    def test_bad_repeats_fails_loud(self):
        with self.assertRaises(bc.BenchControlError):
            bc.build_interleave(0, 3, seed=1)

    def test_negative_warmup_fails_loud(self):
        with self.assertRaises(bc.BenchControlError):
            bc.build_interleave(5, -1, seed=1)


class ControlledCompare(unittest.TestCase):
    def test_produces_verdict_and_restores_affinity(self):
        m = FakeMachine(4)
        clock = _Clock()
        verdict, control = bc.controlled_compare(
            clock.costing(5.0),  # baseline: every run costs 5 ticks
            clock.costing(1.0),  # candidate: every run costs 1 tick (strictly faster)
            repeats=6,
            warmup=1,
            seed=3,
            timer=clock.read,
            setter=m.setter,
            getter=m.getter,
            ncpu=m.ncpu,
        )
        self.assertTrue(control.pinned)  # auto-picked and pinned the quiet core (3)
        self.assertEqual(control.requested_core, 3)
        # candidate is deterministically faster -> the verdict must credit it, not call noise a gain
        self.assertEqual(verdict.label, bp.VERIFIED_IMPROVEMENT)
        self.assertGreater(verdict.delta, 0)
        # affinity restored to the full machine after the run (last setter call)
        self.assertEqual(m.set_calls[-1], {0, 1, 2, 3})

    def test_affinity_restored_even_when_measurement_raises(self):
        m = FakeMachine(4)
        clock = _Clock()

        def boom() -> None:
            raise RuntimeError("workload blew up mid-measure")  # noqa: TRY003

        with self.assertRaises(RuntimeError):
            bc.controlled_compare(
                boom,
                clock.costing(1.0),
                repeats=6,
                warmup=1,
                timer=clock.read,
                setter=m.setter,
                getter=m.getter,
                ncpu=m.ncpu,
            )
        self.assertEqual(m.set_calls[-1], {0, 1, 2, 3})  # restored despite the exception


class Render(unittest.TestCase):
    def test_render_names_conditions_and_defensibility(self):
        m = FakeMachine(4)
        clock = _Clock()
        verdict, control = bc.controlled_compare(
            clock.costing(5.0),
            clock.costing(1.0),
            repeats=6,
            warmup=1,
            timer=clock.read,
            setter=m.setter,
            getter=m.getter,
            ncpu=m.ncpu,
        )
        out = bc.render_controlled(verdict, control)
        self.assertIn("controlled bench verdict", out)
        self.assertIn("affinity achieved", out)
        self.assertIn("defensible", out)


# --- test doubles -----------------------------------------------------------------------------


def _missing() -> _TmpText:
    """An isolated-cpus path that does not exist (OSError on read -> no isolated cores)."""
    return _TmpText(None)


class _TmpText:
    """A Path-like whose read_text returns scripted content (or raises when content is None)."""

    def __init__(self, content: str | None):
        self._content = content

    def read_text(self, *_a, **_k) -> str:
        if self._content is None:
            raise OSError("no such file")  # noqa: TRY003
        return self._content


if __name__ == "__main__":
    unittest.main()
