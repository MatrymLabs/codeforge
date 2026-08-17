"""CARD: bench_protocol -- noise-controlled measurement so a gain inside noise is not called a gain.

RD-2026-0002 #16. The optimization ethos SAYS "a gain inside measurement noise is not a gain" and
"never call a refactor optimized", but nothing implemented the controls that make that real: the
fleet's benches run on whatever cpu governor and core the host happens to schedule, and report a
median ratio with no effect size. This is the discipline the EASE-2025 study prescribes -
warm-up/cool-down, randomized run order, single-core awareness, and a Cliff's-delta EFFECT SIZE that
turns "X is faster" into an honest verdict on the optimization-ethos label ladder.

The pure core (`cliffs_delta`, `compare_samples`) is deterministic and needs no clock - given two
sample sets it returns VERIFIED_IMPROVEMENT / LIKELY_IMPROVEMENT / NEUTRAL / REGRESSION /
INCONCLUSIVE. `measure` uses an INJECTED timer (tests pass a scripted clock; real use passes
`time.perf_counter`). `describe_environment` reports whether noise was actually controlled (the cpu
governor, whether a core was pinned) so the evidence is honest about its conditions - it does not
pretend to SET them (that is `cpufreq-set`/`taskset` at the shell, named in the report).

Convention: LOWER is better (latency/time). Clean-room, stdlib only.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Optimization-ethos honest labels (never "optimized" without evidence).
VERIFIED_IMPROVEMENT = "verified_improvement"
LIKELY_IMPROVEMENT = "likely_improvement"
NEUTRAL = "neutral"
REGRESSION = "regression"
INCONCLUSIVE = "inconclusive"

# Cliff's delta magnitude thresholds (Romano et al. 2006): |d| below negligible == within noise.
_NEGLIGIBLE = 0.147
_SMALL = 0.33
_MEDIUM = 0.474

_MIN_SAMPLES = 5  # below this the effect size is not trustworthy -> inconclusive


class BenchProtocolError(ValueError):
    """Raised on a malformed measurement request (e.g. empty samples where required)."""


def cliffs_delta(baseline: list[float], candidate: list[float]) -> float:
    """Cliff's delta in [-1, 1]: the chance candidate BEATS baseline minus the chance it loses.

    LOWER is better: a candidate value 'beats' a baseline value when it is smaller. delta > 0 means
    the candidate tends faster; delta < 0 slower. Non-parametric (no normality assumed)."""
    if not baseline or not candidate:
        raise BenchProtocolError("cliffs_delta needs non-empty sample sets")  # noqa: TRY003
    faster = slower = 0
    for b in baseline:
        for c in candidate:
            if c < b:
                faster += 1
            elif c > b:
                slower += 1
    return (faster - slower) / (len(baseline) * len(candidate))


def _magnitude(delta: float) -> str:
    d = abs(delta)
    if d < _NEGLIGIBLE:
        return "negligible"
    if d < _SMALL:
        return "small"
    if d < _MEDIUM:
        return "medium"
    return "large"


@dataclass(frozen=True)
class Comparison:
    """The honest verdict on a baseline-vs-candidate measurement."""

    label: str  # one of the ethos labels
    delta: float  # Cliff's delta (>0 candidate faster)
    magnitude: str  # negligible | small | medium | large
    median_ratio: float  # median(candidate) / median(baseline); <1 = faster
    detail: str


def compare_samples(baseline: list[float], candidate: list[float]) -> Comparison:
    """Turn two sample sets into an honest verdict. The core rule: a NEGLIGIBLE effect size is
    NEUTRAL, whatever the median moved - a difference inside the noise band is not a gain."""
    if len(baseline) < _MIN_SAMPLES or len(candidate) < _MIN_SAMPLES:
        return Comparison(
            INCONCLUSIVE,
            0.0,
            "negligible",
            (statistics.median(candidate) / statistics.median(baseline))
            if baseline and candidate
            else 0.0,
            f"too few samples (need >= {_MIN_SAMPLES} each) - inconclusive",
        )
    delta = cliffs_delta(baseline, candidate)
    mag = _magnitude(delta)
    ratio = round(statistics.median(candidate) / statistics.median(baseline), 4)

    if mag == "negligible":
        label = NEUTRAL
        detail = (
            f"effect size negligible (d={delta:.3f}); median ratio {ratio} is within the noise band"
        )
    elif delta > 0:  # candidate faster
        label = VERIFIED_IMPROVEMENT if mag in ("medium", "large") else LIKELY_IMPROVEMENT
        detail = f"candidate faster: d={delta:.3f} ({mag}), median x{ratio}"
    else:  # candidate slower
        label = REGRESSION
        detail = f"candidate slower: d={delta:.3f} ({mag}), median x{ratio}"
    return Comparison(label, round(delta, 4), mag, ratio, detail)


def measure(
    fn: Callable[[], object],
    *,
    repeats: int = 30,
    warmup: int = 3,
    timer: Callable[[], float],
) -> list[float]:
    """Time `fn` `repeats` times (discarding `warmup` initial runs), returning per-run seconds.

    The timer is injected (a monotonic clock in real use; a scripted clock in tests) so measurement
    is deterministic to test. Warm-up runs are discarded to shed cold-start noise (JIT/cache)."""
    if repeats < 1:
        raise BenchProtocolError("repeats must be >= 1")  # noqa: TRY003
    samples: list[float] = []
    for i in range(warmup + repeats):
        start = timer()
        fn()
        elapsed = timer() - start
        if i >= warmup:
            samples.append(elapsed)
    return samples


def run_comparison(
    baseline_fn: Callable[[], object],
    candidate_fn: Callable[[], object],
    *,
    repeats: int = 30,
    warmup: int = 3,
    timer: Callable[[], float],
    order: list[str] | None = None,
) -> Comparison:
    """Measure both functions with INTERLEAVED (order-controlled) runs, then compare honestly.

    `order` is the run order (a list of "b"/"c"); randomize it at the call site (a seeded Random)
    so drift/thermal trends do not systematically favor one function. Defaults to strict
    alternation. Both accumulate `repeats` samples after `warmup` discarded runs each."""
    order = order or (["b", "c"] * repeats)
    base_t = {"b": baseline_fn, "c": candidate_fn}
    warmed = {"b": 0, "c": 0}
    baseline: list[float] = []
    candidate: list[float] = []
    for which in order:
        start = timer()
        base_t[which]()
        elapsed = timer() - start
        if warmed[which] < warmup:
            warmed[which] += 1
            continue
        (baseline if which == "b" else candidate).append(elapsed)
    return compare_samples(baseline, candidate)


def describe_environment(cpu: int = 0) -> dict[str, str]:
    """Report whether measurement noise was actually controlled (advisory, read-only).

    Reads the cpu governor from sysfs when present; it does NOT change it (that is `cpufreq-set`
    + `taskset` at the shell). An honest artifact names its own conditions - a fixed governor and
    a pinned core are what make an effect-size verdict defensible."""
    gov_path = Path(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_governor")
    try:
        governor = gov_path.read_text("utf-8").strip()
    except OSError:
        governor = "unknown (sysfs not readable)"
    controlled = governor in ("performance", "userspace")
    return {
        "cpu_governor": governor,
        "governor_controlled": "yes"
        if controlled
        else "no (results carry frequency-scaling noise)",
        "how_to_control": "cpufreq-set -g performance; taskset -c <core>; randomize run order",
    }


def render(comparison: Comparison, environment: dict[str, str] | None = None) -> str:
    """A human-readable, honest bench verdict."""
    lines = [
        f"bench verdict: {comparison.label.upper()}",
        f"  {comparison.detail}",
    ]
    if environment is not None:
        lines.append(
            f"  environment: governor={environment['cpu_governor']} "
            f"controlled={environment['governor_controlled']}"
        )
    return "\n".join(lines)
