"""CARD: evolution.validation -- the genome gate: reject invalid genotypes before expression.

A DNA-like constraint pre-check (Nguyen et al., 2023; Milenkovic & Pan, 2023): some design
states should simply be inexpressible - illegal dependency combinations, autonomous mutation,
self-approval. This gate returns a typed `ConstraintResult` per rule (so a reviewer sees WHY),
and `validate_genome` fails loud on any blocking violation, the same discipline as every other
CodeForge loader gate. It carries the v1 KeelGate rules: a genome may never declare autonomous
mutation or self-approval, so the evolution layer can never quietly route around Josh.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from parts.evolution.genome import (
    APPROVAL_POLICIES,
    EXPRESSION_TARGETS,
    GENOME_STATUSES,
    MUTATION_POLICIES,
    BlueprintGenome,
    GenomeError,
)

_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")  # frozen-identifier rule, as elsewhere in the repo

# Severities, from the report's constraint model. Only `hard_constraint` is blocking.
HARD = "hard_constraint"
SOFT = "soft_constraint"
WARNING = "warning"
HUMAN_REVIEW = "human_review_required"


@dataclass(frozen=True)
class ConstraintResult:
    """One rule's verdict on a genome, with the evidence a human needs to judge it."""

    passed: bool
    rule_id: str
    severity: str  # hard_constraint | soft_constraint | warning | human_review_required
    summary: str
    blocking: bool
    recommended_action: str = ""


def _fail(rule_id: str, severity: str, summary: str, action: str) -> ConstraintResult:
    return ConstraintResult(
        passed=False,
        rule_id=rule_id,
        severity=severity,
        summary=summary,
        blocking=(severity == HARD),
        recommended_action=action,
    )


def check_constraints(genome: BlueprintGenome) -> list[ConstraintResult]:
    """Every failing rule for this genome, most-blocking first. Empty == fully clean.

    Only violations are returned (an empty list means the genome passed every rule), so a
    reviewer reads exactly what is wrong and why, never a wall of green.
    """
    out: list[ConstraintResult] = []

    if not _LABEL.match(genome.genome_id):
        out.append(
            _fail(
                "GEN01",
                HARD,
                f"genome_id '{genome.genome_id}' is not lowercase_snake_case",
                "rename the genome to a frozen lowercase_snake_case label",
            )
        )
    if not genome.purpose.strip():
        out.append(_fail("GEN02", HARD, "purpose is empty", "state what this genome is for"))
    if genome.status not in GENOME_STATUSES:
        out.append(
            _fail(
                "GEN03",
                HARD,
                f"status '{genome.status}' is not a known status",
                "use a GENOME_STATUSES value",
            )
        )
    # KeelGate: the evolution layer can never declare autonomous mutation or self-approval in v1.
    if genome.mutation_policy not in MUTATION_POLICIES:
        out.append(
            _fail(
                "GEN04",
                HARD,
                f"mutation_policy '{genome.mutation_policy}' is not permitted in v1",
                "set mutation_policy to 'manual_only'; autonomous mutation needs Josh's ok",
            )
        )
    if genome.approval_policy not in APPROVAL_POLICIES:
        out.append(
            _fail(
                "GEN05",
                HARD,
                f"approval_policy '{genome.approval_policy}' is not permitted in v1",
                "set approval_policy to 'human_required'; a genome may never self-approve",
            )
        )
    bad_targets = [t for t in genome.expression_targets if t not in EXPRESSION_TARGETS]
    if bad_targets:
        out.append(
            _fail(
                "GEN06",
                HARD,
                f"unknown expression target(s): {', '.join(bad_targets)}",
                f"expression_targets must be a subset of {EXPRESSION_TARGETS}",
            )
        )
    # DNA-like illegal combination: a dependency cannot be both allowed and prohibited.
    conflict = sorted(set(genome.allowed_dependencies) & set(genome.prohibited_dependencies))
    if conflict:
        out.append(
            _fail(
                "GEN07",
                HARD,
                f"dependency both allowed and prohibited: {', '.join(conflict)}",
                "remove the dependency from one of the two lists",
            )
        )
    # Soft signals (non-blocking): a genome with obligations reads as portfolio-grade.
    if not genome.test_obligations:
        out.append(
            _fail(
                "GEN08",
                WARNING,
                "no test_obligations declared",
                "declare what a phenotype must prove",
            )
        )
    if not genome.documentation_obligations:
        out.append(
            _fail(
                "GEN09",
                WARNING,
                "no documentation_obligations declared",
                "declare the docs a phenotype owes",
            )
        )
    out.sort(key=lambda r: (not r.blocking, r.rule_id))
    return out


def constraints_ok(genome: BlueprintGenome) -> bool:
    """True when no BLOCKING constraint fails (warnings are allowed)."""
    return not any(r.blocking for r in check_constraints(genome))


def validate_genome(genome: BlueprintGenome) -> BlueprintGenome:
    """Return the genome if it passes every blocking rule; else raise GenomeError (a GATE).

    The loud path: a genome that violates a hard constraint never proceeds to expression.
    """
    blocking = [r for r in check_constraints(genome) if r.blocking]
    if blocking:
        detail = "; ".join(f"{r.rule_id}: {r.summary}" for r in blocking)
        raise GenomeError(f"genome {genome.genome_id!r} failed validation -- {detail}")
    return genome
