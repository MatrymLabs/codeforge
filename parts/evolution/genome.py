"""CARD: evolution.genome -- the Blueprint Genome: the typed genotype of a design.

Genotype/phenotype separation (Pantridge & Helmuth, 2023): the genome carries design INTENT
and CONSTRAINTS as typed, inspectable data, kept separate from any emitted code (the
phenotype). It COMPOSES the existing human-authored Blueprint (`parts/blueprint.py`, the seed:
intent, requirements, tasks) and adds the machine-evolution fields the evolutionary literature
needs. State is the JSON; this model never emits code and never mutates the world.

Deliberately NOT an opaque mini-language: every field is a typed primitive/tuple, documented,
and round-trips through `to_dict`/`from_dict`. Frozen and hashable, mirroring `Blueprint`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from parts import blueprint as bp

# The evolution status ladder (elite-baseline preservation, per the report). A genome is never
# promoted up this ladder automatically; promotion past `qualified` is a human decision.
GENOME_STATUSES = (
    "experimental",
    "candidate",
    "qualified",
    "elite",
    "rejected",
    "quarantined",
    "archived",
    "human_review_required",
)

# Where a genome is allowed to express (the phenotype artifact kinds). Kept small in v1.
EXPRESSION_TARGETS = ("code", "tests", "config", "docs")

# v1 governance: a genome may never declare autonomous mutation or self-approval. These are the
# only values the KeelGate (validation.py) accepts until Josh approves a wider policy.
MUTATION_POLICIES = ("manual_only",)  # no autonomous mutation in v1
APPROVAL_POLICIES = ("human_required",)  # Josh promotes, always


class GenomeError(ValueError):
    """A malformed Blueprint Genome -- fail loud at the gate, never evolve a bad genotype."""


@dataclass(frozen=True)
class BlueprintGenome:
    """One design's genotype: the human-authored seed plus the typed evolution constraints.

    Every collection is a tuple (frozen + hashable, like `Blueprint`). Pairs are
    `(key, value)` tuples so budgets/provenance stay ordered, diffable, and JSON-simple.
    """

    genome_id: str  # permanent lowercase_snake_case label (a frozen identifier)
    seed: bp.Blueprint  # the human-authored genotype seed (intent / requirements / tasks)
    purpose: str
    interfaces: tuple[str, ...] = ()  # public signatures the phenotype must expose
    invariants: tuple[str, ...] = ()  # properties that must always hold
    allowed_dependencies: tuple[str, ...] = ()
    prohibited_dependencies: tuple[str, ...] = ()
    resource_budgets: tuple[tuple[str, str], ...] = ()  # (metric, budget) e.g. ("render_us", "50")
    security_policies: tuple[str, ...] = ()
    test_obligations: tuple[str, ...] = ()
    documentation_obligations: tuple[str, ...] = ()
    expression_targets: tuple[str, ...] = ()  # subset of EXPRESSION_TARGETS
    mutation_policy: str = "manual_only"  # v1: no autonomous mutation
    approval_policy: str = "human_required"  # v1: Josh promotes, always
    status: str = "experimental"
    provenance: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (key, value) audit


def _pairs(raw: Any, name: str, genome_id: str) -> tuple[tuple[str, str], ...]:
    """Coerce a mapping OR a list of 2-item pairs into an ordered tuple of (str, str) pairs."""
    if raw is None:
        return ()
    items = raw.items() if isinstance(raw, dict) else raw
    out: list[tuple[str, str]] = []
    try:
        for key, value in items:
            out.append((str(key), str(value)))
    except (TypeError, ValueError) as exc:
        raise GenomeError(f"genome {genome_id!r}: '{name}' must be pairs of (key, value)") from exc
    return tuple(out)


def _strs(raw: Any, name: str, genome_id: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str) or not hasattr(raw, "__iter__"):
        raise GenomeError(f"genome {genome_id!r}: '{name}' must be a list of strings")
    return tuple(str(item) for item in raw)


def from_dict(raw: Any) -> BlueprintGenome:
    """Parse a genome from a plain dict (the JSON shape). A bad field fails loud."""
    if not isinstance(raw, dict):
        raise GenomeError("a genome record must be a mapping")
    genome_id = str(raw.get("genome_id", "")).strip()
    if not genome_id:
        raise GenomeError("genome record missing 'genome_id'")
    if "seed" not in raw:
        raise GenomeError(f"genome {genome_id!r}: missing 'seed' (the Blueprint)")
    try:
        seed = bp.from_dict(raw["seed"])
    except bp.BlueprintError as exc:
        raise GenomeError(f"genome {genome_id!r}: seed is not a valid Blueprint: {exc}") from exc
    return BlueprintGenome(
        genome_id=genome_id,
        seed=seed,
        purpose=str(raw.get("purpose", "")).strip(),
        interfaces=_strs(raw.get("interfaces"), "interfaces", genome_id),
        invariants=_strs(raw.get("invariants"), "invariants", genome_id),
        allowed_dependencies=_strs(
            raw.get("allowed_dependencies"), "allowed_dependencies", genome_id
        ),
        prohibited_dependencies=_strs(
            raw.get("prohibited_dependencies"), "prohibited_dependencies", genome_id
        ),
        resource_budgets=_pairs(raw.get("resource_budgets"), "resource_budgets", genome_id),
        security_policies=_strs(raw.get("security_policies"), "security_policies", genome_id),
        test_obligations=_strs(raw.get("test_obligations"), "test_obligations", genome_id),
        documentation_obligations=_strs(
            raw.get("documentation_obligations"), "documentation_obligations", genome_id
        ),
        expression_targets=_strs(raw.get("expression_targets"), "expression_targets", genome_id),
        mutation_policy=str(raw.get("mutation_policy", "manual_only")),
        approval_policy=str(raw.get("approval_policy", "human_required")),
        status=str(raw.get("status", "experimental")),
        provenance=_pairs(raw.get("provenance"), "provenance", genome_id),
    )


def to_dict(genome: BlueprintGenome) -> dict[str, Any]:
    """Serialize a genome to a plain dict (the JSON shape). Round-trips with `from_dict`."""
    return {
        "genome_id": genome.genome_id,
        "seed": bp.to_dict(genome.seed),
        "purpose": genome.purpose,
        "interfaces": list(genome.interfaces),
        "invariants": list(genome.invariants),
        "allowed_dependencies": list(genome.allowed_dependencies),
        "prohibited_dependencies": list(genome.prohibited_dependencies),
        "resource_budgets": [list(pair) for pair in genome.resource_budgets],
        "security_policies": list(genome.security_policies),
        "test_obligations": list(genome.test_obligations),
        "documentation_obligations": list(genome.documentation_obligations),
        "expression_targets": list(genome.expression_targets),
        "mutation_policy": genome.mutation_policy,
        "approval_policy": genome.approval_policy,
        "status": genome.status,
        "provenance": [list(pair) for pair in genome.provenance],
    }
