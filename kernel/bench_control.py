"""CARD: bench_control -- pin the process to a quiet core, then drive an effect-size A/B, so a
bench verdict names the conditions it was actually measured under.

bench_protocol has the statistics (Cliff's-delta effect size, interleaved order, honest labels)
but its `describe_environment` deliberately only READS the machine: it reports whether the governor
is fixed and names `cpufreq-set`/`taskset` as the missing control, without setting anything. So
every fleet bench today measures on whatever core the scheduler happens to hand it - and a heavy
bench under multi-process contention can even time out (the nav bench did, under a 4-session load).
That noise is exactly what an effect-size label is supposed to defend against, yet nothing pins.

This closes that gap with the stdlib alone - no dependency, no `taskset` subprocess: `os
.sched_setaffinity` narrows the process to one chosen core, `quiet_core` picks the least-contended
one (kernel-isolated cores first, else the highest-numbered), and `controlled_compare` seeds a
reproducible interleave and hands it to `bench_protocol.run_comparison`. The ControlReport is
HONEST about what it actually achieved: a pin that the OS refused (EPERM) reports `pinned=False`
with the reason rather than crashing, and an `ondemand` governor is flagged as uncontrolled noise -
the verdict still stands, it just names its own conditions.

Every OS boundary is an injected seam (`setter`/`getter`/`ncpu`/`timer`), so the whole runner is
deterministic to test on a simulated machine with no real second core. Linux-only in effect
(affinity is a Linux primitive); on a host without it the runner degrades to an honest unpinned
measurement rather than failing. Clean-room, stdlib only.
"""

from __future__ import annotations

import contextlib
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.bench_protocol import Comparison, describe_environment, run_comparison

# Injected-seam type aliases: the three OS calls the runner leans on, so tests can simulate a
# machine (a fake set of cores, a scheduler that refuses the pin) without a real second core.
AffinitySetter = Callable[[int, set[int]], None]  # signature of os.sched_setaffinity
AffinityGetter = Callable[[int], set[int]]  # signature of os.sched_getaffinity
CpuCounter = Callable[[], int | None]  # signature of os.cpu_count


class BenchControlError(ValueError):
    """Raised on an impossible control request (e.g. a core index outside the machine)."""


@dataclass(frozen=True)
class ControlReport:
    """What the runner ACTUALLY achieved - the honest conditions behind an effect-size verdict."""

    requested_core: int | None  # the core we tried to pin to (None = no pin attempted)
    achieved_affinity: tuple[int, ...]  # the cores the process is on after the attempt
    pinned: bool  # True only if affinity narrowed to exactly the requested core
    governor: str  # the cpu governor read from sysfs
    governor_controlled: bool  # True for performance/userspace (no frequency-scaling noise)
    note: str  # a plain-language account of what happened (why a pin failed, etc.)

    def is_defensible(self) -> bool:
        """A verdict is defensible when BOTH knobs were controlled: a pinned core and a fixed
        governor. Anything less still produces a verdict - it just carries named noise."""
        return self.pinned and self.governor_controlled


def _cpu_count(ncpu: CpuCounter) -> int:
    """The machine's core count, failing loud if the OS cannot report one (never guess)."""
    n = ncpu()
    if not n or n < 1:
        raise BenchControlError("cannot determine cpu count - refusing to guess a core layout")
    return n


def quiet_core(
    *,
    getter: AffinityGetter = os.sched_getaffinity,
    ncpu: CpuCounter = os.cpu_count,
    isolated_path: Path = Path("/sys/devices/system/cpu/isolated"),
) -> int:
    """Pick the least-contended core to pin to.

    Preference order: a kernel-isolated core (nothing else is scheduled there) that we are actually
    allowed to run on, else the highest-numbered available core (core 0 fields most interrupts, so
    it is the worst choice). Returns a core index guaranteed to be in the process's current
    affinity mask, so the subsequent pin cannot silently fail on an off-limits core."""
    available = getter(0)
    if not available:
        raise BenchControlError("empty affinity mask - the OS reports no runnable core")

    isolated = _read_isolated(isolated_path)
    usable_isolated = sorted(c for c in isolated if c in available)
    if usable_isolated:
        return usable_isolated[-1]

    _cpu_count(ncpu)  # validate the machine reports a sane layout before trusting the mask
    return max(available)


def _read_isolated(isolated_path: Path) -> set[int]:
    """Parse the kernel `isolcpus` list (e.g. "2-3" or "1,3") from sysfs; empty when none/unset."""
    try:
        raw = isolated_path.read_text("utf-8").strip()
    except OSError:
        return set()
    if not raw:
        return set()
    cores: set[int] = set()
    for part in raw.split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            cores.update(range(int(lo), int(hi) + 1))
        else:
            cores.add(int(part))
    return cores


def pin_process(
    core: int,
    *,
    setter: AffinitySetter = os.sched_setaffinity,
    getter: AffinityGetter = os.sched_getaffinity,
    ncpu: CpuCounter = os.cpu_count,
    cpu_for_governor: int | None = None,
) -> ControlReport:
    """Pin THIS process to `core` and report - honestly - what the OS actually granted.

    Validation fails loud: a negative core, or one at/above the machine's count, is a programming
    error (BenchControlError). A scheduler that refuses the pin (EPERM under a cgroup/cpuset) is
    NOT an error - it is a condition, reported as `pinned=False` with the reason, because the bench
    can still run unpinned and say so. Governor noise is read for the pinned core."""
    n = _cpu_count(ncpu)
    if core < 0 or core >= n:
        raise BenchControlError(f"core {core} is outside this machine's cores 0..{n - 1}")

    note: str
    try:
        setter(0, {core})
        note = f"pinned to core {core}"
    except OSError as exc:  # EPERM under a cpuset/cgroup, or an off-limits core
        note = f"pin refused by the OS ({exc.__class__.__name__}: {exc}); measuring unpinned"

    achieved = tuple(sorted(getter(0)))
    pinned = achieved == (core,)
    if not pinned and "refused" not in note:
        note = f"requested core {core} but affinity is {list(achieved)}; not exclusively pinned"

    env = describe_environment(core if cpu_for_governor is None else cpu_for_governor)
    return ControlReport(
        requested_core=core,
        achieved_affinity=achieved,
        pinned=pinned,
        governor=env["cpu_governor"],
        governor_controlled=env["governor_controlled"] == "yes",
        note=note,
    )


def build_interleave(repeats: int, warmup: int, *, seed: int) -> list[str]:
    """A reproducible, shuffled run order of "b"/"c" for `run_comparison`.

    Both functions need `warmup + repeats` runs; the order is shuffled by a SEEDED Random so
    thermal/drift trends do not systematically favour whichever function runs first, while the
    same seed reproduces the same schedule exactly (an evidence artifact must be repeatable)."""
    if repeats < 1:
        raise BenchControlError("repeats must be >= 1")
    if warmup < 0:
        raise BenchControlError("warmup must be >= 0")
    total = warmup + repeats
    order = ["b"] * total + ["c"] * total
    random.Random(seed).shuffle(order)  # noqa: S311  # nosec B311
    return order


def controlled_compare(
    baseline_fn: Callable[[], object],
    candidate_fn: Callable[[], object],
    *,
    repeats: int = 30,
    warmup: int = 3,
    seed: int = 0,
    core: int | None = None,
    timer: Callable[[], float] = time.perf_counter,
    setter: AffinitySetter = os.sched_setaffinity,
    getter: AffinityGetter = os.sched_getaffinity,
    ncpu: CpuCounter = os.cpu_count,
) -> tuple[Comparison, ControlReport]:
    """Measure baseline vs candidate on a pinned quiet core with a seeded interleave, then restore
    the original affinity. Returns the honest effect-size verdict AND the conditions it holds under.

    `core=None` auto-selects a quiet core. The original affinity is always restored (a bench must
    not leave the process pinned for whatever runs next), even if measurement raises."""
    target = quiet_core(getter=getter, ncpu=ncpu) if core is None else core
    original = getter(0)
    control = pin_process(target, setter=setter, getter=getter, ncpu=ncpu)
    try:
        order = build_interleave(repeats, warmup, seed=seed)
        verdict = run_comparison(
            baseline_fn,
            candidate_fn,
            repeats=repeats,
            warmup=warmup,
            timer=timer,
            order=order,
        )
    finally:
        if original:  # put the process back where we found it (best-effort restore)
            with contextlib.suppress(OSError):
                setter(0, set(original))
    return verdict, control


def render_controlled(verdict: Comparison, control: ControlReport) -> str:
    """A human-readable, honest controlled-bench verdict: the result AND its conditions."""
    defensible = "yes" if control.is_defensible() else "no (see conditions)"
    return "\n".join(
        [
            f"controlled bench verdict: {verdict.label.upper()}",
            f"  {verdict.detail}",
            f"  conditions: {control.note}; governor={control.governor} "
            f"(controlled={'yes' if control.governor_controlled else 'no'})",
            f"  affinity achieved: {list(control.achieved_affinity)}",
            f"  defensible (pinned AND fixed governor): {defensible}",
        ]
    )
