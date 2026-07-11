"""CARD: evolution.bakeoff -- the Blueprint Evolution Lab run: score a population, ask Josh.

The orchestrator that proves the whole data flow end to end: validate the genome (gate),
run a small hand-authored candidate population through the evaluator swarm, apply multi-
objective fitness (hard gates first), turn every hard-gate failure into a counterexample,
preserve the elite baseline, rank the survivors -- and STOP. Nothing is promoted; the run
ends `human_decision_required`. v1 limits are explicit (<= 3 candidates, a kill switch) and
there is no autonomous mutation: the strategies are hand-authored.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field

from parts.evolution.candidate import Candidate
from parts.evolution.counterexamples import Counterexample, CounterexampleBank
from parts.evolution.evaluators import EvaluatorResult, run_evaluators
from parts.evolution.fitness import WEIGHTS, FitnessResult, _Entry, aggregate_fitness
from parts.evolution.genome import BlueprintGenome
from parts.evolution.subjects import (
    ORACLE_INPUTS,
    Formatter,
    candidate_extensible,
    candidate_minimal,
    candidate_performance,
    oracle_fit,
)
from parts.evolution.validation import validate_genome

MAX_CANDIDATES = 3  # v1 cost limit (per the report); raising it later needs evidence.


class BakeoffError(RuntimeError):
    """The run could not proceed (bad genome, too many candidates, or the kill switch)."""


@dataclass(frozen=True)
class CandidateOutcome:
    """One candidate's full result: the record (with disposition), its scores, its evidence."""

    candidate: Candidate
    fitness: FitnessResult
    evaluator_results: tuple[EvaluatorResult, ...]


@dataclass(frozen=True)
class EvolutionRun:
    """One reproducible bake-off: the population, the winner (unpromoted), and the evidence."""

    run_id: str
    genome_id: str
    elite_baseline: str
    outcomes: tuple[CandidateOutcome, ...]
    counterexamples: tuple[Counterexample, ...] = field(default_factory=tuple)
    winner: str | None = None  # top qualified candidate; disposition stays `qualified`
    final_status: str = "human_decision_required"


def _source_lines(fn: Formatter) -> int:
    try:
        return len(inspect.getsource(fn).strip().splitlines())
    except (OSError, TypeError):  # pragma: no cover - a C/builtin fn has no readable source
        return 1


def run_bakeoff(
    genome: BlueprintGenome,
    pairs: list[tuple[Candidate, Formatter]],
    run_id: str,
    inputs: tuple[tuple[str, int], ...] = ORACLE_INPUTS,
    oracle: Formatter = oracle_fit,
    bank: CounterexampleBank | None = None,
    elite_baseline: str = "oracle_fit",
    kill_switch: bool = False,
) -> EvolutionRun:
    """Run the population and return the evidence. Never promotes; ends human_decision_required."""
    if kill_switch:
        raise BakeoffError("kill switch engaged -- run aborted before any candidate executed")
    if len(pairs) > MAX_CANDIDATES:
        raise BakeoffError(f"v1 allows at most {MAX_CANDIDATES} candidates; got {len(pairs)}")
    validate_genome(genome)  # the constraint gate: a bad genome never reaches the population

    bank = bank if bank is not None else CounterexampleBank()
    entries: list[_Entry] = []
    results_by_id: dict[str, list[EvaluatorResult]] = {}
    for candidate, fn in pairs:
        results = run_evaluators(candidate.candidate_id, fn, inputs, oracle)
        results_by_id[candidate.candidate_id] = results
        entries.append(_Entry(candidate.candidate_id, results, _source_lines(fn)))
        # A correctness failure becomes a counterexample: permanent regression knowledge.
        correctness = next(r for r in results if r.evaluator_id == "correctness")
        if correctness.status == "fail":
            for finding in correctness.findings:
                bank.add(
                    affected=genome.genome_id,
                    failing_input=finding,
                    expected="oracle output",
                    actual="candidate output",
                    candidate_id=candidate.candidate_id,
                )

    fitnesses = {f.candidate_id: f for f in aggregate_fitness(entries)}
    outcomes: list[CandidateOutcome] = []
    for candidate, _fn in pairs:
        fitness = fitnesses[candidate.candidate_id]
        disposition = "qualified" if fitness.hard_gate_status == "pass" else "rejected"
        outcomes.append(
            CandidateOutcome(
                candidate=candidate.with_disposition(disposition),
                fitness=fitness,
                evaluator_results=tuple(results_by_id[candidate.candidate_id]),
            )
        )

    qualified = [o for o in outcomes if o.fitness.overall_weighted is not None]
    winner = (
        max(qualified, key=lambda o: o.fitness.overall_weighted or 0.0).candidate.candidate_id
        if qualified
        else None
    )
    return EvolutionRun(
        run_id=run_id,
        genome_id=genome.genome_id,
        elite_baseline=elite_baseline,
        outcomes=tuple(outcomes),
        counterexamples=tuple(bank.all()),
        winner=winner,
    )


def build_score_sheet_pairs(genome_id: str) -> list[tuple[Candidate, Formatter]]:
    """The three hand-authored ScoreSheetRenderer column-formatter candidates."""
    return [
        (
            Candidate(
                "cand_minimal", genome_id, "minimal", "candidate_minimal", ("elite_baseline",)
            ),
            candidate_minimal,
        ),
        (
            Candidate("cand_performance", genome_id, "performance", "candidate_performance"),
            candidate_performance,
        ),
        (
            Candidate("cand_extensible", genome_id, "extensibility", "candidate_extensible"),
            candidate_extensible,
        ),
    ]


def render_run(run: EvolutionRun) -> str:
    """Render the run as a human-selection report: every metric visible, Josh decides."""
    lines = [
        f"BLUEPRINT EVOLUTION LAB -- run {run.run_id}",
        f"  genome: {run.genome_id}   elite baseline: {run.elite_baseline}",
        f"  objectives + weights: {', '.join(f'{n} x{w}' for n, w in WEIGHTS)}",
        "",
        "CANDIDATES",
    ]
    for out in run.outcomes:
        f = out.fitness
        gate = f.hard_gate_status.upper()
        score = f"{f.overall_weighted:.3f}" if f.overall_weighted is not None else "  --  "
        lines.append(
            f"  [{gate:4}] {out.candidate.candidate_id:16} ({out.candidate.strategy}) w={score}"
        )
        if f.hard_gate_status == "fail":
            for reason in f.hard_gate_reasons:
                lines.append(f"        x hard gate: {reason}")
        for obj in f.objectives:
            lines.append(
                f"        - {obj.name:14} raw={obj.raw:<10.3f} norm={obj.normalized:.3f} "
                f"x{obj.weight} = {obj.contribution:.3f}"
            )
    lines += ["", "COUNTEREXAMPLES (permanent regression knowledge)"]
    if run.counterexamples:
        for c in run.counterexamples:
            lines.append(f"  - [{c.first_seen}] {c.failing_input}  (x{c.occurrences})")
    else:
        lines.append("  (none -- every candidate preserved the contract)")
    lines += [
        "",
        f"TOP QUALIFIED: {run.winner or '(none passed the hard gates)'}",
        f"STATUS: {run.final_status.upper()} -- no candidate is promoted; Josh selects the elite.",
    ]
    return "\n".join(lines)
