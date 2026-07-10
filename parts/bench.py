"""CARD: bench -- performance evidence: how fast is the engine tick?

The engine tick (`handle_command`) is the one door to the world (architecture law 4). This
measures its throughput and latency over a read-only command rotation, so "fast" is a number
with a distribution, not a claim. Frameless: stdlib `time` + `statistics`, no benchmark
framework. The rotation never mutates world state (renders are projections), so the run is
stable and repeatable. `make bench` runs it and files a dated evidence report; the test twin
rides `make check` with a tiny sample count.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from pathlib import Path

# Read-only commands: exercise dispatch plus a spread of real handlers without mutating
# state (so successive samples are comparable and the measurement does not drift).
_ROTATION = ("look", "help", "score", "inventory")


class BenchError(ValueError):
    """Reject a nonsensical benchmark request, loudly, rather than measure noise."""


@dataclass(frozen=True)
class BenchResult:
    """The measured distribution of one benchmark run."""

    samples: int
    commands: tuple[str, ...]
    throughput_per_s: float
    median_us: float
    p95_us: float
    p99_us: float
    max_us: float


def benchmark(
    iterations: int = 20_000,
    warmup: int = 500,
    rotation: tuple[str, ...] = _ROTATION,
) -> BenchResult:
    """Drive the tick `iterations` times over the rotation and report the distribution."""
    if iterations <= 0:
        raise BenchError(f"iterations must be > 0, got {iterations}")
    if warmup < 0:
        raise BenchError(f"warmup must be >= 0, got {warmup}")
    if not rotation:
        raise BenchError("rotation must name at least one command")

    from forge import handle_command  # lazy: the tick is the top, parts do not import it eagerly
    from parts.session import Session

    session = Session(player_id="_bench")
    perf = time.perf_counter

    for i in range(warmup):  # first calls resolve imports and build the command table
        handle_command(session, rotation[i % len(rotation)])

    latencies_us: list[float] = []
    loop_start = perf()
    for i in range(iterations):
        command = rotation[i % len(rotation)]
        call_start = perf()
        handle_command(session, command)
        latencies_us.append((perf() - call_start) * 1e6)
    loop_total_s = perf() - loop_start

    latencies_us.sort()
    return BenchResult(
        samples=iterations,
        commands=tuple(rotation),
        throughput_per_s=(iterations / loop_total_s) if loop_total_s > 0 else 0.0,
        median_us=statistics.median(latencies_us),
        p95_us=latencies_us[int(0.95 * (iterations - 1))],
        p99_us=latencies_us[int(0.99 * (iterations - 1))],
        max_us=latencies_us[-1],
    )


def render_bench(result: BenchResult) -> str:
    """The human/terminal report of a benchmark run."""
    return "\n".join(
        [
            "ENGINE TICK BENCHMARK - handle_command throughput (read-only rotation)",
            f"  commands   : {', '.join(result.commands)}",
            f"  samples    : {result.samples:,}",
            f"  throughput : {result.throughput_per_s:,.0f} commands/sec",
            f"  latency    : median {result.median_us:.1f}us  p95 {result.p95_us:.1f}us  "
            f"p99 {result.p99_us:.1f}us  max {result.max_us:.1f}us",
            "",
            "  Renders never mutate state (architecture law 1), so the rotation is repeatable.",
            "  Measured on this host; numbers scale with CPU. Reproducible: `make bench`.",
        ]
    )


def write_bench_report(
    result: BenchResult, root: Path | None = None, stamp: str | None = None
) -> Path:
    """File the run as dated performance evidence under reports/performance/."""
    from parts.reporting import write_report

    return write_report(
        "performance", render_bench(result), root=root, stamp=stamp, slug="engine-tick"
    )


def bench(arg: str = "") -> str:
    """The in-game / terminal `bench`: a quick, responsive run (small sample)."""
    return render_bench(benchmark(iterations=5_000, warmup=200))


def main(argv: list[str] | None = None) -> int:
    """`make bench`: run the full benchmark, print it, and file the evidence report."""
    result = benchmark()
    print(render_bench(result))
    path = write_bench_report(result)
    print(f"\n  evidence -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
