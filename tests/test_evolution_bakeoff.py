"""Test twin for the Blueprint Evolution Lab bake-off (parts/evolution/bakeoff.py + friends).

The headline guarantees: the correct candidates pass the hard gate and the contract-breaking
one is rejected AND recorded as a counterexample; a fitness score never promotes anything (the
run ends human_decision_required); and the v1 limits + kill switch + genome gate all hold.
"""

from __future__ import annotations

import pytest

from parts import blueprint as bp
from parts.evolution.bakeoff import (
    MAX_CANDIDATES,
    BakeoffError,
    build_score_sheet_pairs,
    render_run,
    run_bakeoff,
)
from parts.evolution.candidate import Candidate
from parts.evolution.counterexamples import CounterexampleBank
from parts.evolution.genome import BlueprintGenome, GenomeError
from parts.evolution.subjects import candidate_minimal


def _genome(**over: object) -> BlueprintGenome:
    seed = bp.Blueprint(
        "fit_column", "Fit Column", "Fit text to a fixed width.", ("pure",), ("no untrusted input",)
    )
    base: dict[str, object] = dict(
        genome_id="fit_column",
        seed=seed,
        purpose="Evolve a fixed-width column formatter.",
        test_obligations=("matches the oracle on every input",),
        documentation_obligations=("docstring",),
        expression_targets=("code", "tests"),
    )
    base.update(over)
    return BlueprintGenome(**base)  # type: ignore[arg-type]


def _run():
    return run_bakeoff(_genome(), build_score_sheet_pairs("fit_column"), run_id="test-001")


def test_the_contract_preserving_candidates_qualify_and_the_breaker_is_rejected() -> None:
    run = _run()
    disp = {o.candidate.candidate_id: o.candidate.disposition for o in run.outcomes}
    assert disp["cand_minimal"] == "qualified"
    assert disp["cand_performance"] == "qualified"
    assert disp["cand_extensible"] == "rejected"  # changed observable behavior on truncation


def test_a_hard_gate_failure_earns_no_weighted_score() -> None:
    run = _run()
    ext = next(o for o in run.outcomes if o.candidate.candidate_id == "cand_extensible")
    assert ext.fitness.hard_gate_status == "fail"
    assert ext.fitness.overall_weighted is None  # no score is earned past a failed hard gate
    assert ext.fitness.hard_gate_reasons  # and the reason is visible


def test_qualified_candidates_show_every_objective() -> None:
    run = _run()
    good = next(o for o in run.outcomes if o.candidate.candidate_id == "cand_minimal")
    names = {obj.name for obj in good.fitness.objectives}
    assert names == {"runtime", "documentation", "maintainability"}
    assert good.fitness.overall_weighted is not None


def test_the_breaker_becomes_a_counterexample() -> None:
    run = _run()
    assert run.counterexamples, "the contract break must be recorded as regression knowledge"
    assert any(c.first_seen == "cand_extensible" for c in run.counterexamples)


def test_nothing_is_auto_promoted() -> None:
    run = _run()
    assert run.final_status == "human_decision_required"
    assert run.winner in {"cand_minimal", "cand_performance"}  # a survivor, but only 'qualified'
    assert all(o.candidate.disposition != "elite" for o in run.outcomes)  # never elite by machine


def test_the_report_shows_metrics_and_the_human_decision() -> None:
    out = render_run(_run())
    assert "BLUEPRINT EVOLUTION LAB" in out
    assert "COUNTEREXAMPLES" in out
    assert "HUMAN_DECISION_REQUIRED" in out
    assert "runtime" in out and "documentation" in out  # objectives are visible


def test_the_counterexample_bank_dedups_a_repeat() -> None:
    bank = CounterexampleBank()
    first = bank.add("fit_column", "fit('abcdef',3) -> 'ab>'", "abc", "ab>", "cand_extensible")
    again = bank.add("fit_column", "fit('abcdef',3) -> 'ab>'", "abc", "ab>", "cand_other")
    assert len(bank) == 1  # one signature
    assert again.occurrences == 2 and again.status == "duplicate"
    assert first.occurrences == 1


def test_too_many_candidates_is_refused() -> None:
    genome = _genome()
    pairs = build_score_sheet_pairs("fit_column")
    extra = pairs + [
        (Candidate("cand_x", "fit_column", "x", "candidate_minimal"), candidate_minimal)
    ]
    assert len(extra) > MAX_CANDIDATES
    with pytest.raises(BakeoffError, match="at most"):
        run_bakeoff(genome, extra, run_id="test-002")


def test_the_kill_switch_aborts_before_any_candidate_runs() -> None:
    with pytest.raises(BakeoffError, match="kill switch"):
        run_bakeoff(_genome(), build_score_sheet_pairs("fit_column"), run_id="k", kill_switch=True)


def test_with_disposition_rejects_an_unknown_value() -> None:
    cand = Candidate("c", "g", "minimal", "candidate_minimal")
    with pytest.raises(ValueError, match="unknown disposition"):
        cand.with_disposition("promoted_by_robot")


def test_bank_serializes_to_dicts() -> None:
    bank = CounterexampleBank()
    bank.add("fit_column", "fit('x',1)->'y'", "x", "y", "cand")
    rows = bank.to_dicts()
    assert rows and rows[0]["first_seen"] == "cand" and rows[0]["status"] == "new"


def test_a_run_with_only_passing_candidates_reports_no_counterexamples() -> None:
    pairs = build_score_sheet_pairs("fit_column")[:2]  # minimal + performance only
    out = render_run(run_bakeoff(_genome(), pairs, run_id="clean"))
    assert "(none" in out  # no contract break -> no counterexamples


def test_a_candidate_that_raises_is_a_correctness_failure() -> None:
    from parts.evolution.evaluators import evaluate_correctness
    from parts.evolution.subjects import oracle_fit

    def boom(text: str, width: int) -> str:
        raise RuntimeError("kaboom")

    result = evaluate_correctness("cand_boom", boom, (("a", 2),), oracle_fit)
    assert result.status == "fail"
    assert "raised" in result.findings[0]


def test_a_self_approving_genome_never_reaches_the_population() -> None:
    # The constraint gate runs first: a genome that violates the KeelGate aborts the run.
    with pytest.raises(GenomeError, match="GEN05"):
        run_bakeoff(
            _genome(approval_policy="auto_promote"),
            build_score_sheet_pairs("fit_column"),
            run_id="bad",
        )
