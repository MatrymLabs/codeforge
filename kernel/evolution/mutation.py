"""CARD: evolution.mutation -- propose new candidate genomes by typed operators (propose-only).

The Blueprint Evolution Lab shipped every rung EXCEPT the generative one: bakeoff.py SELECTS among
hand-authored genomes, it never PROPOSES new ones. This adds that step under a strict keel (opened
by Josh for HC-13). Typed, deterministic operators derive new candidate genomes from existing ones,
and every proposal:

  1. passes the SAME `validate_genome` KeelGate (an invalid genotype is dropped, never emitted);
  2. carries `mutation_policy="propose_only"` and `approval_policy="human_required"`;
  3. is returned as `status="candidate"` for the SAME human-approved bake-off - never promoted to
     qualified/elite, never merged, never marked autonomous.

AI proposes; the gate validates; Josh decides. This is FunSearch-style variation (Romera-Paredes
et al., 2024) with the selection authority left human - the exact line kernel/evolution/genome.py
draws. The operators are ENUMERATIVE (no RNG), so a run is deterministic and reproducible.

No new dependency (dataclasses + the existing genome/validation parts). No world state is touched:
this function returns records, it writes nothing and promotes nothing.
"""

from __future__ import annotations

import re
from dataclasses import replace

from kernel.evolution.genome import BlueprintGenome, GenomeError
from kernel.evolution.validation import validate_genome

# The keel constants this module is contractually bound to. A proposal that ever drifts off these
# is a bug the test twin pins: propose, never self-approve, never autonomous.
_PROPOSE = "propose_only"
_HUMAN = "human_required"
_CANDIDATE = "candidate"

_LABEL_OK = re.compile(r"^[a-z][a-z0-9_]*$")
_NONWORD = re.compile(r"[^a-z0-9]+")


class MutationError(ValueError):
    """A malformed mutation request (e.g. a seed that is not a valid genome)."""


def _slug(text: str) -> str:
    """Sanitize a fragment into a lowercase_snake_case id piece (never empty, always a-z start)."""
    s = _NONWORD.sub("_", text.lower()).strip("_")
    if not s or not s[0].isalpha():
        s = f"g_{s}" if s else "g"
    return s


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _propose(
    parent: BlueprintGenome,
    *,
    suffix: str,
    operator: str,
    parents: tuple[str, ...],
    **changes: object,
) -> BlueprintGenome | None:
    """Build a proposed genome from a parent + field changes, stamp the keel, and gate it.

    Returns the validated proposal, or None if it fails the KeelGate (fail-closed: a proposal that
    would not pass validation for a human is never surfaced as one). The keel fields are forced
    here, not taken from the caller, so no operator can accidentally propose an autonomous genome.
    """
    new_id = f"{parent.genome_id}_{_slug(suffix)}"
    if not _LABEL_OK.match(new_id):  # defensive: the id must stay a frozen label (GEN01)
        return None
    provenance = (
        *parent.provenance,
        ("mutation_operator", operator),
        ("parents", " + ".join(parents)),
        ("proposed_by", "evolution.mutation (propose-only)"),
    )
    proposal = replace(
        parent,
        genome_id=new_id,
        status=_CANDIDATE,
        mutation_policy=_PROPOSE,  # forced: AI proposes
        approval_policy=_HUMAN,  # forced: only Josh promotes
        provenance=provenance,
        **changes,  # type: ignore[arg-type]
    )
    try:
        return validate_genome(proposal)
    except GenomeError:
        return None  # a proposal that fails the gate is dropped, never raised into the population


def drop_dependency(genome: BlueprintGenome) -> list[BlueprintGenome]:
    """Propose one leaner variant per allowed dependency, each dropping exactly that dependency."""
    out: list[BlueprintGenome] = []
    for dep in genome.allowed_dependencies:
        leaner = tuple(d for d in genome.allowed_dependencies if d != dep)
        cand = _propose(
            genome,
            suffix=f"less_{dep}",
            operator=f"drop_dependency:{dep}",
            parents=(genome.genome_id,),
            allowed_dependencies=leaner,
        )
        if cand is not None:
            out.append(cand)
    return out


def harden_dependency(genome: BlueprintGenome) -> list[BlueprintGenome]:
    """Propose one stricter variant per allowed dependency, moving it allowed -> prohibited."""
    out: list[BlueprintGenome] = []
    for dep in genome.allowed_dependencies:
        if dep in genome.prohibited_dependencies:
            continue  # already prohibited elsewhere; skip (would be a no-op / GEN07 risk)
        cand = _propose(
            genome,
            suffix=f"no_{dep}",
            operator=f"harden_dependency:{dep}",
            parents=(genome.genome_id,),
            allowed_dependencies=tuple(d for d in genome.allowed_dependencies if d != dep),
            prohibited_dependencies=(*genome.prohibited_dependencies, dep),
        )
        if cand is not None:
            out.append(cand)
    return out


def scale_budgets(genome: BlueprintGenome, *, factor: float = 0.9) -> BlueprintGenome | None:
    """Propose a more-demanding variant: scale every NUMERIC resource budget by `factor`.

    The convention here is cost-style budgets (latency_us, bytes, ms) where smaller is stricter, so
    factor<1 proposes a tighter target; non-numeric budgets are left untouched. Returns None when
    the genome has no numeric budget to scale (nothing to propose). The human/fitness judges whether
    tighter is actually better - this only offers the variant.
    """
    if not 0 < factor < 1:
        raise MutationError(f"scale factor must be in (0, 1), got {factor}")
    scaled: list[tuple[str, str]] = []
    touched = False
    for metric, value in genome.resource_budgets:
        if _is_number(value):
            scaled.append((metric, _format_number(float(value) * factor)))
            touched = True
        else:
            scaled.append((metric, value))
    if not touched:
        return None
    return _propose(
        genome,
        suffix="tighter",
        operator=f"scale_budgets:{factor}",
        parents=(genome.genome_id,),
        resource_budgets=tuple(scaled),
    )


def crossover(parent_a: BlueprintGenome, parent_b: BlueprintGenome) -> BlueprintGenome | None:
    """Recombine two parents into one child genome (classic GA crossover, fully typed).

    The child UNIONs the safety-additive fields (invariants, prohibited deps, security, test +
    doc obligations, interfaces) and INTERSECTS allowed_dependencies (only what BOTH parents
    permit), so a crossover never widens the dependency surface past either parent. For a budget
    both parents set, the stricter (smaller numeric) value wins. Returns None if the child fails
    the gate.
    """
    child_budgets = _merge_budgets(parent_a.resource_budgets, parent_b.resource_budgets)
    return _propose(
        parent_a,
        suffix=f"x_{parent_b.genome_id}",
        operator="crossover",
        parents=(parent_a.genome_id, parent_b.genome_id),
        purpose=parent_a.purpose or parent_b.purpose,
        interfaces=_union(parent_a.interfaces, parent_b.interfaces),
        invariants=_union(parent_a.invariants, parent_b.invariants),
        allowed_dependencies=_intersect(
            parent_a.allowed_dependencies, parent_b.allowed_dependencies
        ),
        prohibited_dependencies=_union(
            parent_a.prohibited_dependencies, parent_b.prohibited_dependencies
        ),
        security_policies=_union(parent_a.security_policies, parent_b.security_policies),
        test_obligations=_union(parent_a.test_obligations, parent_b.test_obligations),
        documentation_obligations=_union(
            parent_a.documentation_obligations, parent_b.documentation_obligations
        ),
        resource_budgets=child_budgets,
    )


def propose_variants(genome: BlueprintGenome, *, factor: float = 0.9) -> list[BlueprintGenome]:
    """Run every unary operator on one genome; return the valid proposals (may be empty).

    Refuses a seed that is not itself a valid genome (fail loud on the INPUT; a bad seed is a
    caller error, unlike a mutant that merely fails the gate and is silently dropped).
    """
    try:
        validate_genome(genome)
    except GenomeError as exc:
        raise MutationError(f"cannot mutate an invalid seed genome: {exc}") from exc
    proposals = [*drop_dependency(genome), *harden_dependency(genome)]
    tighter = scale_budgets(genome, factor=factor)
    if tighter is not None:
        proposals.append(tighter)
    return proposals


def propose_crossovers(population: list[BlueprintGenome]) -> list[BlueprintGenome]:
    """Pairwise-crossover a population into valid child proposals (each unordered pair once)."""
    for g in population:
        try:
            validate_genome(g)
        except GenomeError as exc:
            raise MutationError(f"cannot cross an invalid genome {g.genome_id!r}: {exc}") from exc
    out: list[BlueprintGenome] = []
    for i, a in enumerate(population):
        for b in population[i + 1 :]:
            child = crossover(a, b)
            if child is not None:
                out.append(child)
    return out


def render(proposals: list[BlueprintGenome]) -> str:
    """A human-readable summary of proposed candidates (propose-only: a human reads, then decides).

    A human reads this and chooses; nothing here promotes anything.
    """
    if not proposals:
        return "evolution.mutation: no proposals (nothing to vary)"
    header = f"evolution.mutation: {len(proposals)} proposed candidate(s) - human_decision_required"
    lines = [header]
    for p in proposals:
        op = dict(p.provenance).get("mutation_operator", "?")
        lines.append(f"  {p.genome_id}  [{op}]  policy={p.mutation_policy}/{p.approval_policy}")
    return "\n".join(lines)


# ---- small typed helpers (kept private; pure) ----


def _union(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    """Order-preserving union: everything in a, then anything new from b."""
    out = list(a)
    for item in b:
        if item not in out:
            out.append(item)
    return tuple(out)


def _intersect(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    bset = set(b)
    return tuple(item for item in a if item in bset)


def _merge_budgets(
    a: tuple[tuple[str, str], ...], b: tuple[tuple[str, str], ...]
) -> tuple[tuple[str, str], ...]:
    """Merge two budget lists; for a shared numeric metric keep the stricter (smaller) value."""
    merged: dict[str, str] = dict(a)
    for metric, value in b:
        if metric in merged and _is_number(value) and _is_number(merged[metric]):
            merged[metric] = _format_number(min(float(merged[metric]), float(value)))
        else:
            merged.setdefault(metric, value)
    return tuple(merged.items())


def _format_number(value: float) -> str:
    """Render a float without a trailing '.0' when it is integral (keeps budgets tidy)."""
    return str(int(value)) if value == int(value) else str(value)
