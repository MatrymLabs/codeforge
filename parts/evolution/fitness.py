"""CARD: evolution.fitness -- multi-objective fitness: hard gates first, then weighted objectives.

Do not choose a candidate by one score (Solovyeva et al., 2025). A candidate that fails a HARD
gate (correctness here) cannot be promoted, full stop. Only after the hard gates do weighted
objectives (runtime, documentation, maintainability) produce an overall score -- and every raw
and normalized objective stays VISIBLE, so a human sees exactly why a candidate ranked where it
did. No single number hides the components.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parts.evolution.evaluators import EvaluatorResult

# The weighted objectives and their weights (v1 defaults; visible and documented on purpose).
WEIGHTS: tuple[tuple[str, float], ...] = (
    ("runtime", 0.5),
    ("documentation", 0.2),
    ("maintainability", 0.3),
)

_PASS, _FAIL = "pass", "fail"


@dataclass(frozen=True)
class ObjectiveScore:
    """One weighted objective for one candidate -- raw AND normalized, so nothing is hidden."""

    name: str
    raw: float  # the measured value (us, lines, 0/1)
    normalized: float  # 0.0..1.0, higher is better, comparable across candidates
    weight: float
    contribution: float  # normalized * weight


@dataclass(frozen=True)
class FitnessResult:
    """A candidate's fitness: the hard-gate verdict, then the visible weighted objectives."""

    candidate_id: str
    hard_gate_status: str  # pass | fail
    hard_gate_reasons: tuple[str, ...]
    objectives: tuple[ObjectiveScore, ...] = field(default_factory=tuple)
    overall_weighted: float | None = None  # None when a hard gate failed (no score is earned)
    human_review_required: bool = True  # a fitness score never promotes; Josh decides


def _hard_gate(results: list[EvaluatorResult]) -> tuple[str, tuple[str, ...]]:
    """Fail if any blocking evaluator failed. Returns (status, reasons)."""
    reasons = [
        f"{r.evaluator_id}: {r.findings[0] if r.findings else 'failed'}"
        for r in results
        if r.blocking and r.status == _FAIL
    ]
    return (_FAIL if reasons else _PASS, tuple(reasons))


def _metric(results: list[EvaluatorResult], evaluator_id: str, key: str, default: float) -> float:
    for r in results:
        if r.evaluator_id == evaluator_id:
            for name, value in r.metrics:
                if name == key:
                    return value
            return default  # pragma: no cover - evaluator present but metric absent (defensive)
    return default  # pragma: no cover - evaluator absent (defensive)


def _doc_score(results: list[EvaluatorResult]) -> float:
    return next((r.score for r in results if r.evaluator_id == "documentation"), 0.0)


@dataclass
class _Entry:
    """A candidate's inputs to fitness: its evaluator results and its source size."""

    candidate_id: str
    results: list[EvaluatorResult]
    source_lines: int


def aggregate_fitness(entries: list[_Entry]) -> list[FitnessResult]:
    """Score a whole population: hard gates first, then normalize the objectives across the
    candidates that passed (so 'best runtime in the population' means something)."""
    passing = [e for e in entries if _hard_gate(e.results)[0] == _PASS]
    # Best-in-population reference values, over the passing candidates only.
    best_us = min(
        (_metric(e.results, "performance", "median_us", 1e9) for e in passing), default=1.0
    )
    best_lines = min((max(e.source_lines, 1) for e in passing), default=1)

    out: list[FitnessResult] = []
    for entry in entries:
        status, reasons = _hard_gate(entry.results)
        if status == _FAIL:
            out.append(FitnessResult(entry.candidate_id, status, reasons))
            continue
        us = _metric(entry.results, "performance", "median_us", 1e9)
        lines = max(entry.source_lines, 1)
        raw_norm = {
            "runtime": (us, best_us / us if us else 0.0),
            "documentation": (_doc_score(entry.results), _doc_score(entry.results)),
            "maintainability": (float(lines), best_lines / lines),
        }
        objectives = tuple(
            ObjectiveScore(
                name, raw_norm[name][0], raw_norm[name][1], weight, raw_norm[name][1] * weight
            )
            for name, weight in WEIGHTS
        )
        overall = sum(o.contribution for o in objectives)
        out.append(FitnessResult(entry.candidate_id, status, reasons, objectives, overall))
    return out
