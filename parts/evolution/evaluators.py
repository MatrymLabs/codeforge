"""CARD: evolution.evaluators -- the bounded evaluator swarm (advise, never merge).

Specialized read-only evaluators (SOEN-101, 2024, adjacent): each inspects one candidate on
one quality dimension and returns a structured `EvaluatorResult` -- a score, findings, and
evidence. No evaluator writes code, promotes a candidate, or approves its own recommendation;
they only produce signals for the fitness engine and, ultimately, Josh. Conflicting results
are surfaced, never hidden.

v1 ships three: Correctness (blocking hard gate), Documentation, and Performance (advisory).
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from parts.evolution.subjects import Subject

_PASS, _FAIL, _WARN = "pass", "fail", "warn"


@dataclass(frozen=True)
class EvaluatorResult:
    """One evaluator's verdict on one candidate. Advisory: it never merges or promotes."""

    evaluator_id: str
    candidate_id: str
    status: str  # pass | fail | warn
    score: float  # 0.0..1.0, higher is better (this evaluator's own judgment)
    findings: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)
    metrics: tuple[tuple[str, float], ...] = field(default_factory=tuple)  # raw numbers for fitness
    confidence: float = 1.0
    blocking: bool = False


def evaluate_correctness(
    candidate_id: str,
    fn: Subject,
    inputs: tuple[tuple[Any, ...], ...],
    oracle: Subject,
) -> EvaluatorResult:
    """Blocking hard gate: the candidate must match the oracle on every input, exactly.

    Signature-agnostic: each input is an argument tuple applied as `fn(*args)`, so the same
    gate scores a (str, int) formatter and a (str,) slugifier alike."""
    mismatches: list[str] = []
    for args in inputs:
        try:
            got = fn(*args)
        except Exception as exc:  # a candidate that raises is a correctness failure, not a crash
            mismatches.append(f"call{args!r} raised {type(exc).__name__}: {exc}")
            continue
        want = oracle(*args)
        if got != want:
            mismatches.append(f"call{args!r} -> {got!r}, expected {want!r}")
    passed = not mismatches
    score = 1.0 if passed else 1.0 - len(mismatches) / len(inputs)
    return EvaluatorResult(
        evaluator_id="correctness",
        candidate_id=candidate_id,
        status=_PASS if passed else _FAIL,
        score=score,
        findings=tuple(mismatches),
        evidence=tuple(mismatches[:1]),  # the first failing input is the counterexample seed
        blocking=True,
    )


def evaluate_documentation(candidate_id: str, fn: Subject) -> EvaluatorResult:
    """Advisory: does the candidate carry a non-empty docstring?"""
    doc = (fn.__doc__ or "").strip()
    has_doc = bool(doc)
    return EvaluatorResult(
        evaluator_id="documentation",
        candidate_id=candidate_id,
        status=_PASS if has_doc else _WARN,
        score=1.0 if has_doc else 0.0,
        findings=() if has_doc else ("no docstring",),
        evidence=(doc[:60],) if has_doc else (),
    )


def evaluate_performance(
    candidate_id: str,
    fn: Subject,
    inputs: tuple[tuple[Any, ...], ...],
    reps: int = 2000,
    warmup: int = 200,
) -> EvaluatorResult:
    """Advisory: median wall-time (microseconds) over the input set. Raw number for fitness.

    Score is a self-relative placeholder (1.0); the fitness engine normalizes the raw
    `median_us` across the population, so no single number is treated as the whole verdict.
    """
    for _ in range(warmup):
        for args in inputs:
            fn(*args)
    samples: list[float] = []
    for _ in range(reps):
        start = time.perf_counter()
        for args in inputs:
            fn(*args)
        samples.append((time.perf_counter() - start) * 1e6)
    median_us = statistics.median(samples)
    return EvaluatorResult(
        evaluator_id="performance",
        candidate_id=candidate_id,
        status=_PASS,
        score=1.0,
        findings=(f"median {median_us:.2f} us over {len(inputs)} inputs",),
        metrics=(("median_us", median_us),),
    )


def run_evaluators(
    candidate_id: str,
    fn: Subject,
    inputs: tuple[tuple[Any, ...], ...],
    oracle: Subject,
) -> list[EvaluatorResult]:
    """The coordinator: run every evaluator, return their results (assembles, never judges)."""
    return [
        evaluate_correctness(candidate_id, fn, inputs, oracle),
        evaluate_documentation(candidate_id, fn),
        evaluate_performance(candidate_id, fn, inputs),
    ]
