"""CARD: loadtest -- concurrent load evidence: does the tick's latency hold up under many sessions?

`kernel/bench.py` measures the engine tick single-threaded: the best case, one caller. A load test
asks the harder question the SLO cares about: when many players hit the world at once, does per
command latency stay bounded, or does it fall off a cliff? This drives `handle_command` from
`concurrency` worker threads at once (each with its own `Session`, over the same read-only rotation
`bench` uses, so state never mutates and the run is repeatable), starts them together on a barrier
for real contention, and captures the latency DISTRIBUTION under load: p50, p95, p99, max,
throughput, and error count.

It measures a real CodeForge workload, not a synthetic one, and it claims nothing it did not
measure. Honest about Python: the tick is CPU-bound and the GIL serializes bytecode, so this does
not show linear speedup and is not meant to -- it shows how latency and throughput behave when
`concurrency` connections contend for one interpreter, which is exactly the threaded gateway's
condition. The result feeds the engine-tick SLO (`kernel/slo.py`): `compare_to_slo` reports whether
p50 under load still meets the objective, closing the loop from measurement to objective to budget.

Frameless: stdlib `threading`, `time`, `statistics`. In-process and localhost-only -- it drives the
tick directly, touching no network and nothing it does not own. `make loadtest` files a dated
evidence report; the test twin rides `make check` with tiny parameters.

Provenance: original implementation. "Load testing as a committed artifact (latency histograms that
feed an SLO and postmortem)" is the documented practice; no code copied.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

# The same read-only rotation bench uses: exercises dispatch and a spread of handlers without
# mutating world state, so concurrent workers never race on a write and the run is repeatable.
_ROTATION = ("look", "help", "score", "inventory")


class LoadError(ValueError):
    """Reject a nonsensical load request (non-positive concurrency or work), loudly."""


@dataclass(frozen=True)
class LoadResult:
    """The measured latency distribution of one concurrent load run."""

    concurrency: int
    per_worker: int
    total_calls: int
    commands: tuple[str, ...]
    duration_s: float
    throughput_per_s: float
    p50_us: float
    p95_us: float
    p99_us: float
    max_us: float
    errors: int


def _percentile(sorted_us: list[float], fraction: float) -> float:
    """The value at `fraction` of a sorted latency list (nearest-rank, matching kernel/bench.py)."""
    if not sorted_us:
        return 0.0
    idx = int(fraction * (len(sorted_us) - 1))
    return sorted_us[idx]


def run_load(
    concurrency: int = 8,
    per_worker: int = 2_000,
    *,
    rotation: tuple[str, ...] = _ROTATION,
    warmup: int = 200,
) -> LoadResult:
    """Drive the tick from `concurrency` threads, each issuing `per_worker` commands, and report the
    latency distribution under contention.

    Fails loud (`LoadError`) on concurrency < 1, per_worker < 1, warmup < 0, or an empty rotation.
    Threads are pre-seeded with their own Session and released together on a barrier, so the run
    measures genuine concurrent load rather than staggered starts.
    """
    if concurrency < 1:
        raise LoadError(f"concurrency must be >= 1, got {concurrency}")  # noqa: TRY003
    if per_worker < 1:
        raise LoadError(f"per_worker must be >= 1, got {per_worker}")  # noqa: TRY003
    if warmup < 0:
        raise LoadError(f"warmup must be >= 0, got {warmup}")  # noqa: TRY003
    if not rotation:
        raise LoadError("rotation must name at least one command")  # noqa: TRY003

    from forge import handle_command  # lazy: the tick is the top; parts do not import it eagerly  # noqa: E501, I001, PLC0415
    from kernel.world.session import Session  # noqa: PLC0415

    # Warm up single-threaded so first-call import/cache building never races across the workers.
    warm = Session(player_id="_load_warm")
    for i in range(warmup):
        handle_command(warm, rotation[i % len(rotation)])

    sessions = [Session(player_id=f"_load_{w}") for w in range(concurrency)]
    latencies: list[list[float]] = [[] for _ in range(concurrency)]
    errors = [0] * concurrency
    start_gate = threading.Barrier(concurrency + 1)  # +1 for the timer thread (this thread)
    perf = time.perf_counter

    def worker(index: int) -> None:
        session = sessions[index]
        local: list[float] = latencies[index]
        start_gate.wait()  # every worker blocks here until all are ready, then they run together
        for i in range(per_worker):
            command = rotation[i % len(rotation)]
            call_start = perf()
            try:
                handle_command(session, command)
            except Exception:  # noqa: BLE001 - a load test counts failures, never lets one abort it
                errors[index] += 1
            local.append((perf() - call_start) * 1e6)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(concurrency)]
    for t in threads:
        t.start()
    start_gate.wait()  # release all workers at once
    loop_start = perf()
    for t in threads:
        t.join()
    duration_s = perf() - loop_start

    all_us = sorted(us for worker_us in latencies for us in worker_us)
    total_calls = len(all_us)
    return LoadResult(
        concurrency=concurrency,
        per_worker=per_worker,
        total_calls=total_calls,
        commands=tuple(rotation),
        duration_s=duration_s,
        throughput_per_s=(total_calls / duration_s) if duration_s > 0 else 0.0,
        p50_us=_percentile(all_us, 0.50),
        p95_us=_percentile(all_us, 0.95),
        p99_us=_percentile(all_us, 0.99),
        max_us=all_us[-1] if all_us else 0.0,
        errors=sum(errors),
    )


def compare_to_slo(result: LoadResult) -> str:
    """Report whether p50 under this load still meets the engine-tick SLO objective threshold.

    Honest link from load evidence to the objective: the SLI is a single-threaded median, so this
    does not record into that series (different measurement conditions); it answers "does the
    objective still hold under load?" as supporting evidence for the SLO doc.
    """
    from kernel import slo  # noqa: PLC0415

    threshold = slo.DEFAULT_THRESHOLD_US
    verdict = "within" if result.p50_us <= threshold else "OVER"
    return (
        f"  vs SLO      : p50 {result.p50_us:.1f}us is {verdict} the {threshold:g}us objective "
        f"under {result.concurrency}x concurrent load"
    )


def render_load(result: LoadResult) -> str:
    """The human/terminal report of a load run."""
    return "\n".join(
        [
            "ENGINE TICK LOAD TEST - handle_command under concurrent sessions (read-only rotation)",
            f"  commands    : {', '.join(result.commands)}",
            f"  concurrency : {result.concurrency} sessions x {result.per_worker} calls each "  # noqa: ISC004
            f"= {result.total_calls:,} calls",
            f"  duration    : {result.duration_s:.3f}s",
            f"  throughput  : {result.throughput_per_s:,.0f} commands/sec (aggregate)",
            f"  latency     : p50 {result.p50_us:.1f}us  p95 {result.p95_us:.1f}us  "  # noqa: ISC004
            f"p99 {result.p99_us:.1f}us  max {result.max_us:.1f}us",
            f"  errors      : {result.errors}",
            compare_to_slo(result),
            "",
            "  Read-only rotation (renders never mutate state), so the run is repeatable.",
            "  Python is GIL-bound: this shows latency-under-contention, not linear speedup.",
            "  Measured on this host; reproducible: `make loadtest`.",
        ]
    )


def write_load_report(
    result: LoadResult, root: Path | None = None, stamp: str | None = None
) -> Path:
    """File the run as dated performance evidence under reports/performance/."""
    from kernel.shelf.reporting import write_report  # noqa: PLC0415

    return write_report(
        "performance", render_load(result), root=root, stamp=stamp, slug="engine-tick-load"
    )


def loadtest(arg: str = "") -> str:  # noqa: ARG001
    """The in-game / terminal `loadtest`: a quick, responsive concurrent run (small sample)."""
    return render_load(run_load(concurrency=4, per_worker=500, warmup=100))


def main(argv: list[str] | None = None) -> int:
    """`make loadtest`: run the full concurrent load test, print it, and file the evidence report.

    Optional args: `loadtest [concurrency] [per_worker]`. Returns 1 if any call errored (a load
    test that produced errors is not a clean result), else 0.
    """
    import sys  # noqa: PLC0415

    args = list(sys.argv[1:] if argv is None else argv)
    try:
        concurrency = int(args[0]) if len(args) > 0 else 8
        per_worker = int(args[1]) if len(args) > 1 else 2_000
        result = run_load(concurrency=concurrency, per_worker=per_worker)
    except (LoadError, ValueError) as exc:
        print(f"load test failed: {exc}")
        return 2
    print(render_load(result))
    path = write_load_report(result)
    print(f"\n  evidence -> {path}")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
