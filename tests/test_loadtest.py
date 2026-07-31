"""Test twin for parts/loadtest.py: the concurrent engine-tick load test.

Acceptance AND refusal cases, with tiny parameters so it rides make check. A load test's own
correctness is: it runs the requested number of calls across the requested workers, produces an
ordered latency distribution, records no errors on the read-only rotation, and refuses nonsensical
requests.
"""

from __future__ import annotations

import pytest

from parts import loadtest


def test_runs_requested_calls_across_workers() -> None:
    result = loadtest.run_load(concurrency=3, per_worker=40, warmup=10)
    assert result.concurrency == 3
    assert result.per_worker == 40
    assert result.total_calls == 120  # 3 workers x 40 calls
    assert result.errors == 0  # the read-only rotation never faults


def test_percentiles_are_ordered_and_positive() -> None:
    result = loadtest.run_load(concurrency=2, per_worker=60, warmup=10)
    assert 0.0 < result.p50_us <= result.p95_us <= result.p99_us <= result.max_us
    assert result.throughput_per_s > 0.0
    assert result.duration_s > 0.0


def test_single_worker_is_allowed() -> None:
    # concurrency=1 is a valid degenerate load (equivalent to a serial run).
    result = loadtest.run_load(concurrency=1, per_worker=25, warmup=5)
    assert result.total_calls == 25
    assert result.errors == 0


def test_render_mentions_slo_and_metrics() -> None:
    result = loadtest.run_load(concurrency=2, per_worker=30, warmup=5)
    text = loadtest.render_load(result)
    assert "LOAD TEST" in text
    assert "vs SLO" in text  # the honest link to the objective
    assert "p50" in text and "throughput" in text


def test_compare_to_slo_reports_within_or_over() -> None:
    result = loadtest.run_load(concurrency=2, per_worker=30, warmup=5)
    line = loadtest.compare_to_slo(result)
    assert ("within" in line) or ("OVER" in line)


# --- Refusal ---------------------------------------------------------------------------------


@pytest.mark.parametrize("concurrency", [0, -1])
def test_nonpositive_concurrency_refused(concurrency: int) -> None:
    with pytest.raises(loadtest.LoadError):
        loadtest.run_load(concurrency=concurrency, per_worker=10)


@pytest.mark.parametrize("per_worker", [0, -5])
def test_nonpositive_per_worker_refused(per_worker: int) -> None:
    with pytest.raises(loadtest.LoadError):
        loadtest.run_load(concurrency=2, per_worker=per_worker)


def test_negative_warmup_refused() -> None:
    with pytest.raises(loadtest.LoadError):
        loadtest.run_load(concurrency=2, per_worker=10, warmup=-1)


def test_empty_rotation_refused() -> None:
    with pytest.raises(loadtest.LoadError):
        loadtest.run_load(concurrency=2, per_worker=10, rotation=())


def test_main_refuses_bad_args() -> None:
    assert loadtest.main(["not-a-number"]) == 2


def test_verb_runs_a_small_load() -> None:
    # The `loadtest` verb runs a quick concurrent sample and never raises into the caller.
    assert "LOAD TEST" in loadtest.loadtest()


# --- Coverage of the failure and reporting paths ---------------------------------------------


def test_percentile_of_empty_is_zero() -> None:
    assert loadtest._percentile([], 0.5) == 0.0


def test_faulting_command_is_counted_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    # A handler that raises is counted as an error and never aborts the run (warmup=0 so the
    # faulting handler is only hit inside the guarded worker loop).
    import forge

    def _boom(_session: object, _text: str) -> str:
        raise RuntimeError("handler blew up")

    monkeypatch.setattr(forge, "handle_command", _boom)
    result = loadtest.run_load(concurrency=2, per_worker=10, warmup=0)
    assert result.errors == result.total_calls == 20  # every call faulted, none aborted the run


def test_write_report_files_under_root(tmp_path: object) -> None:
    result = loadtest.run_load(concurrency=1, per_worker=10, warmup=2)
    path = loadtest.write_load_report(result, root=tmp_path)  # type: ignore[arg-type]
    assert path.exists()
    assert "LOAD TEST" in path.read_text(encoding="utf-8")


def test_main_success_returns_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    monkeypatch.setattr(loadtest, "write_load_report", lambda r: tmp_path)  # avoid repo fs write
    assert loadtest.main(["1", "5"]) == 0


def test_main_returns_1_when_calls_errored(monkeypatch: pytest.MonkeyPatch) -> None:
    errored = loadtest.LoadResult(
        concurrency=1,
        per_worker=1,
        total_calls=1,
        commands=("look",),
        duration_s=0.01,
        throughput_per_s=100.0,
        p50_us=1.0,
        p95_us=1.0,
        p99_us=1.0,
        max_us=1.0,
        errors=3,
    )
    monkeypatch.setattr(loadtest, "run_load", lambda **k: errored)
    monkeypatch.setattr(loadtest, "write_load_report", lambda r: "x")
    assert loadtest.main([]) == 1
