"""Test twin for kernel/slo.py: the engine-tick SLO + error-budget evaluator.

Acceptance AND refusal cases. Every SLI series is seeded into a tmp Chronicle root, so these
tests never touch the real ledger. Hostile/near-miss data is deliberate: values exactly at the
threshold, values one microsecond over, and sparse series where the budget is not yet meaningful.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import chronicle, slo


def _seed(root: Path, values: list[float]) -> None:
    """File each value as an engine_tick.median_us metric point into a tmp Chronicle."""
    for v in values:
        chronicle.record_metric(slo.SLI_NAME, v, commit="test", root=root)


# --- Acceptance: the happy path -------------------------------------------------------------


def test_all_within_threshold_passes(tmp_path: Path) -> None:
    _seed(tmp_path, [50.0, 58.0, 60.0, 70.0, 149.9])
    v = slo.evaluate(threshold_us=150.0, objective_pct=99.0, root=tmp_path)
    assert v.verdict == "pass"
    assert v.samples == 5
    assert v.bad == 0
    assert v.good == 5
    assert v.attainment_pct == 100.0
    assert v.budget_consumed_pct == 0.0


def test_value_exactly_at_threshold_is_good(tmp_path: Path) -> None:
    # The objective is "<= threshold", so a value sitting exactly on the line does NOT breach.
    _seed(tmp_path, [150.0, 150.0])
    v = slo.evaluate(threshold_us=150.0, objective_pct=99.0, root=tmp_path)
    assert v.bad == 0
    assert v.verdict == "pass"


def test_value_one_micro_over_threshold_is_bad(tmp_path: Path) -> None:
    _seed(tmp_path, [150.01])
    v = slo.evaluate(threshold_us=150.0, objective_pct=99.0, root=tmp_path)
    assert v.bad == 1


# --- Acceptance: the budget verdicts ---------------------------------------------------------


def test_watchlist_when_budget_mostly_burned(tmp_path: Path) -> None:
    # 25 runs, objective 90% -> budget 10% -> allowed_bad 2.5. Two breaches burns 80% of it.
    _seed(tmp_path, [50.0] * 23 + [200.0, 200.0])
    v = slo.evaluate(threshold_us=150.0, objective_pct=90.0, root=tmp_path)
    assert v.bad == 2
    assert v.allowed_bad == pytest.approx(2.5)
    assert v.budget_consumed_pct == pytest.approx(80.0)
    assert v.verdict == "watchlist"


def test_breach_when_budget_overspent(tmp_path: Path) -> None:
    # Same shape, three breaches (3 > 2.5 allowed) -> budget exhausted -> breach.
    _seed(tmp_path, [50.0] * 22 + [200.0, 200.0, 200.0])
    v = slo.evaluate(threshold_us=150.0, objective_pct=90.0, root=tmp_path)
    assert v.bad == 3
    assert v.verdict == "breach"
    assert v.budget_consumed_pct > 100.0


def test_budget_meaningful_flag_false_for_sparse_series(tmp_path: Path) -> None:
    # At 99% objective the budget allows 0.05 breaches over 5 runs (< 1): not yet meaningful.
    _seed(tmp_path, [50.0] * 5)
    v = slo.evaluate(threshold_us=150.0, objective_pct=99.0, root=tmp_path)
    assert v.budget_meaningful is False
    # ...but a full 100 runs makes it meaningful (allowed_bad == 1.0).
    _seed(tmp_path, [50.0] * 95)
    v2 = slo.evaluate(threshold_us=150.0, objective_pct=99.0, root=tmp_path)
    assert v2.samples == 100
    assert v2.allowed_bad == pytest.approx(1.0)
    assert v2.budget_meaningful is True


# --- Refusal: absence and bad inputs ---------------------------------------------------------


def test_no_data_is_honest_not_a_false_pass(tmp_path: Path) -> None:
    v = slo.evaluate(root=tmp_path)  # empty tmp Chronicle
    assert v.verdict == "no-data"
    assert v.samples == 0
    assert v.attainment_pct == 0.0  # not 100: absence must never read as full attainment


def test_nonpositive_threshold_refused(tmp_path: Path) -> None:
    with pytest.raises(slo.SloError):
        slo.evaluate(threshold_us=0.0, root=tmp_path)
    with pytest.raises(slo.SloError):
        slo.evaluate(threshold_us=-1.0, root=tmp_path)


def test_objective_outside_open_interval_refused(tmp_path: Path) -> None:
    for bad in (0.0, 100.0, 150.0, -5.0):
        with pytest.raises(slo.SloError):
            slo.evaluate(objective_pct=bad, root=tmp_path)


# --- Rendering: every verdict renders without crashing ---------------------------------------


@pytest.mark.parametrize(
    "values,objective",
    [
        ([], 99.0),  # no-data
        ([50.0] * 5, 99.0),  # pass, not-meaningful note
        ([50.0] * 23 + [200.0, 200.0], 90.0),  # watchlist
        ([50.0] * 22 + [200.0, 200.0, 200.0], 90.0),  # breach + policy line
    ],
)
def test_render_is_total(tmp_path: Path, values: list[float], objective: float) -> None:
    _seed(tmp_path, values)
    text = slo.render(slo.evaluate(objective_pct=objective, root=tmp_path))
    assert slo.SLI_NAME in text
    assert text.strip()


def test_verb_never_raises_and_mentions_slo() -> None:
    # The `slo` verb reads the real default series and never raises into the tick, whatever the
    # ledger holds (an empty metric series reads as no-data, not a crash).
    assert "SLO" in slo.slo()


def _bind_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Redirect slo.evaluate to read from a tmp Chronicle while keeping its positional signature."""
    real = slo.evaluate

    def _rooted(
        threshold_us: float = slo.DEFAULT_THRESHOLD_US,
        objective_pct: float = slo.DEFAULT_OBJECTIVE_PCT,
        **kwargs: object,
    ) -> slo.SloVerdict:
        return real(threshold_us, objective_pct, root=root)

    monkeypatch.setattr(slo, "evaluate", _rooted)


def test_main_returns_nonzero_on_breach(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, [50.0] * 22 + [200.0, 200.0, 200.0])
    _bind_root(monkeypatch, tmp_path)
    assert slo.main(["150", "90"]) == 1


def test_main_returns_zero_on_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, [50.0] * 5)
    _bind_root(monkeypatch, tmp_path)
    assert slo.main([]) == 0


# --- Refusal: error paths never crash the caller ---------------------------------------------


def test_verb_reports_evaluation_failure_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A tampered/broken ledger surfaces its integrity failure as text, never raising into the tick.
    def _boom(*_a: object, **_k: object) -> list[object]:
        raise chronicle.ChronicleError("broken chain")

    monkeypatch.setattr(chronicle, "trend", _boom)
    out = slo.slo()
    assert "could not be evaluated" in out
    assert "broken chain" in out


def test_main_returns_2_on_bad_objective() -> None:
    # threshold 0 is refused by evaluate -> main catches SloError and returns 2 (not a crash).
    assert slo.main(["0"]) == 2


def test_main_returns_2_on_nonnumeric_arg() -> None:
    # A non-numeric argument is a ValueError from float(); main reports it and returns 2.
    assert slo.main(["not-a-number"]) == 2
