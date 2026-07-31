"""Benchmark: `zone_of` room -> area lookup, linear scan vs the reverse index.

Evidence for the day-209 optimization batch (research mechanism: performance engineering, STRONG).
`zone_of` is on a hot path (every move, room render, and combat beat calls it). The original walked
every area's room list (`room in zone["rooms"]`, a plain list), a scan over ~53k rooms per lookup at
aethryn scale; the reverse index makes it a single dict lookup.

This times both the linear scan (reconstructed here) and the shipped `zone_of` over a realistic
probe (real rooms plus guaranteed misses, the worst case that scans every area). Frameless
(perf_counter + statistics), no test framework. Run at scale with the aethryn seed:

    FORGE_SEED=aethryn python benchmarks/bench_zones.py
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable

from parts.world import zones
from parts.world.world import WORLD


def _linear_zone_of(room: str) -> str | None:
    """The pre-optimization implementation, kept here only to measure what the index replaced."""
    for label, zone in zones.ZONES.items():
        if room in zone["rooms"]:
            return label
    return None


def _median_ms(fn: Callable[[], object], runs: int = 7) -> tuple[float, float]:
    """Median and p95 wall time in ms over `runs` (one warm-up discarded)."""
    fn()  # warm up
    samples = [(_timed(fn)) for _ in range(runs)]
    samples.sort()
    return statistics.median(samples), samples[-1]


def _timed(fn: Callable[[], object]) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def main() -> None:
    z = zones.ZONES
    zoned = sum(len(zone["rooms"]) for zone in z.values())
    hits = list(WORLD)[:2000]
    misses = [f"__no_such_room_{i}" for i in range(2000)]  # worst case: scans every area
    probe = hits + misses
    n = len(probe)

    def run_linear() -> None:
        for r in probe:
            _linear_zone_of(r)

    def run_index() -> None:
        for r in probe:
            zones.zone_of(r)

    print(f"areas={len(z)}  zoned_rooms={zoned}  world_rooms={len(WORLD)}  probe={n}")
    lin_med, lin_p95 = _median_ms(run_linear)
    idx_med, idx_p95 = _median_ms(run_index)
    print(f"linear_scan : median {lin_med:8.3f} ms  p95 {lin_p95:8.3f} ms  "
          f"per_call {lin_med / n * 1000:8.2f} us")  # fmt: skip
    print(f"reverse_idx : median {idx_med:8.3f} ms  p95 {idx_p95:8.3f} ms  "
          f"per_call {idx_med / n * 1000:8.2f} us")  # fmt: skip
    if idx_med > 0:
        print(f"speedup     : {lin_med / idx_med:.1f}x (median)")


if __name__ == "__main__":
    main()
