"""Test twin for parts/bench.py -- the engine-tick benchmark.

Acceptance: a small run measures a sane distribution and files a report. Refusal: a
nonsensical request (zero iterations, negative warmup, empty rotation) fails loud rather
than measuring noise. Sample counts are tiny here so the suite stays fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.bench import (
    BenchError,
    benchmark,
    render_bench,
    write_bench_report,
)


def test_a_small_run_measures_a_sane_distribution() -> None:
    result = benchmark(iterations=300, warmup=20)
    assert result.samples == 300
    assert result.throughput_per_s > 0
    assert result.median_us > 0
    # percentiles are ordered: median <= p95 <= p99 <= max
    assert result.median_us <= result.p95_us <= result.p99_us <= result.max_us
    assert result.commands  # the rotation is recorded


def test_render_shows_throughput_and_latency() -> None:
    out = render_bench(benchmark(iterations=200, warmup=10))
    assert "ENGINE TICK BENCHMARK" in out
    assert "commands/sec" in out
    assert "median" in out and "p95" in out


def test_zero_iterations_fails_loud() -> None:
    with pytest.raises(BenchError, match="iterations must be > 0"):
        benchmark(iterations=0)


def test_negative_warmup_fails_loud() -> None:
    with pytest.raises(BenchError, match="warmup must be >= 0"):
        benchmark(iterations=10, warmup=-1)


def test_empty_rotation_fails_loud() -> None:
    with pytest.raises(BenchError, match="at least one command"):
        benchmark(iterations=10, rotation=())


def test_report_is_filed_as_dated_evidence(tmp_path: Path) -> None:
    result = benchmark(iterations=100, warmup=10)
    path = write_bench_report(result, root=tmp_path, stamp="2026-07-10")
    assert path.exists()
    assert "performance" in str(path)
    assert "ENGINE TICK BENCHMARK" in path.read_text()


def test_bench_reachable_through_the_terminal() -> None:
    from parts.terminal import terminal

    out = terminal("bench")
    assert "ENGINE TICK BENCHMARK" in out
