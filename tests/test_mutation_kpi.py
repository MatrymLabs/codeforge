"""CARD: test_mutation_kpi -- acceptance + refusal for the mutation-score evidence KPI.

Acceptance: a real cosmic-ray summary parses; a fresh run is MEASURED with the right kill rate;
the real fleet baseline (179 mutants, ~68% killed) is MEASURED and honestly breaches the 70% target.
Refusal: no run / stale run / zero mutants are NOT_COMPUTABLE (never a faked 0); incoherent or
malformed reports fail loud, not silent.
"""

from __future__ import annotations

from datetime import date

import pytest

from kernel.shelf.mutation_kpi import (
    MEASURED,
    NOT_COMPUTABLE,
    MutationKpiError,
    MutationResult,
    mutation_score_kpi,
    parse_cr_rate,
    parse_cr_report,
)

TODAY = date(2026, 8, 2)

# Verified-real cr-report summary captured from a genuine cosmic-ray run (RD-2026-0003).
REAL_REPORT_ALL_KILLED = """\
sut.py core/NumberReplacer 3
worker outcome: WorkerOutcome.NORMAL, test outcome: TestOutcome.KILLED
total jobs: 31
complete: 31 (100.00%)
surviving mutants: 0 (0.00%)
"""

# Same VERIFIED-REAL format; survivor numbers from the fleet's real baseline
# (docs/mutation_testing.md: 179 mutants on hashchain.py, ~32% survived / ~68% killed).
FLEET_BASELINE_REPORT = """\
total jobs: 179
complete: 179 (100.00%)
surviving mutants: 57 (31.84%)
"""


def test_real_report_all_killed_is_measured_at_100() -> None:
    result = parse_cr_report(REAL_REPORT_ALL_KILLED, run_date=TODAY)
    assert (result.total, result.killed, result.survived) == (31, 31, 0)
    kpi = mutation_score_kpi(result, TODAY)
    assert kpi.status == MEASURED
    assert kpi.kill_rate == 1.0
    assert kpi.breaches_target is False


def test_fleet_baseline_is_measured_and_honestly_breaches_target() -> None:
    result = parse_cr_report(FLEET_BASELINE_REPORT, run_date=TODAY)
    assert (result.total, result.killed, result.survived) == (179, 122, 57)
    kpi = mutation_score_kpi(result, TODAY)
    assert kpi.status == MEASURED
    assert kpi.kill_rate == pytest.approx(0.68, abs=0.005)
    assert kpi.breaches_target is True  # 68% < 70% -> honest breach, not a rounded pass


def test_incomplete_mutants_are_excluded_from_the_denominator() -> None:
    r = MutationResult(total=100, killed=60, survived=20, incomplete=20, run_date=TODAY)
    assert r.kill_rate == pytest.approx(0.75)  # 60 / (60+20), not 60/100


def test_cr_rate_parses_survival_percent_to_fraction() -> None:
    assert parse_cr_rate("0.00") == 0.0
    assert parse_cr_rate("31.84\n") == pytest.approx(0.3184)


def test_no_run_is_not_computable_not_a_faked_zero() -> None:
    kpi = mutation_score_kpi(None, TODAY)
    assert kpi.status == NOT_COMPUTABLE
    assert kpi.kill_rate is None
    assert "make mutation" in kpi.detail


def test_stale_run_is_not_computable_with_the_age() -> None:
    old = MutationResult(total=179, killed=122, survived=57, run_date=date(2026, 6, 1))
    kpi = mutation_score_kpi(old, TODAY, freshness_days=30)
    assert kpi.status == NOT_COMPUTABLE
    assert "stale" in kpi.detail


def test_zero_mutants_is_not_computable() -> None:
    empty = MutationResult(total=0, killed=0, survived=0, run_date=TODAY)
    assert mutation_score_kpi(empty, TODAY).status == NOT_COMPUTABLE


def test_future_run_date_fails_loud() -> None:
    ahead = MutationResult(total=10, killed=10, survived=0, run_date=date(2026, 9, 1))
    with pytest.raises(MutationKpiError):
        mutation_score_kpi(ahead, TODAY)


def test_incoherent_counts_fail_loud() -> None:
    with pytest.raises(MutationKpiError):
        MutationResult(total=10, killed=8, survived=8, run_date=TODAY)  # 16 > 10
    with pytest.raises(MutationKpiError):
        MutationResult(total=10, killed=-1, survived=0, run_date=TODAY)


def test_malformed_cr_report_fails_loud() -> None:
    with pytest.raises(MutationKpiError):
        parse_cr_report("nothing useful here", run_date=TODAY)
    with pytest.raises(MutationKpiError):
        # surviving (4) > complete (3) -> incoherent
        incoherent = "total jobs: 5\ncomplete: 3 (60%)\nsurviving mutants: 4 (80%)"
        parse_cr_report(incoherent, run_date=TODAY)


def test_malformed_cr_rate_fails_loud() -> None:
    with pytest.raises(MutationKpiError):
        parse_cr_rate("not-a-number")
    with pytest.raises(MutationKpiError):
        parse_cr_rate("150.0")  # out of range
