"""Test twin for parts/bench.py -- the engine-tick benchmark.

Acceptance: a small run measures a sane distribution and files a report. Refusal: a
nonsensical request (zero iterations, negative warmup, empty rotation) fails loud rather
than measuring noise. Sample counts are tiny here so the suite stays fast.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import parts.bench as bench_mod
from parts import chronicle
from parts.bench import (
    BenchError,
    benchmark,
    main,
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


def test_record_flag_appends_the_median_as_a_chronicle_metric(monkeypatch, tmp_path: Path) -> None:
    # `make trend` uses `bench --record <commit>`. Keep it fast and off the real store:
    # a tiny canned run, a no-op report write, and a spy for the metric append.
    canned = benchmark(iterations=50, warmup=5)
    monkeypatch.setattr(bench_mod, "benchmark", lambda: canned)
    monkeypatch.setattr(bench_mod, "write_bench_report", lambda r: tmp_path / "r.md")
    seen: dict[str, object] = {}

    def _spy(name, value, *, commit, root=None, stamp=None):
        seen.update(name=name, value=value, commit=commit)
        return SimpleNamespace(payload={"name": name, "value": value})

    monkeypatch.setattr(chronicle, "record_metric", _spy)
    main(["--record", "deadbee"])
    assert seen["name"] == "engine_tick.median_us"
    assert isinstance(seen["value"], float) and seen["commit"] == "deadbee"


def test_plain_bench_never_touches_the_chronicle(monkeypatch, tmp_path: Path) -> None:
    canned = benchmark(iterations=50, warmup=5)
    monkeypatch.setattr(bench_mod, "benchmark", lambda: canned)
    monkeypatch.setattr(bench_mod, "write_bench_report", lambda r: tmp_path / "r.md")
    called = False

    def _boom(*a, **k):
        nonlocal called
        called = True

    monkeypatch.setattr(chronicle, "record_metric", _boom)
    main([])  # no --record
    assert called is False
