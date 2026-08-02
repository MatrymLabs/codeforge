"""CARD: evolution.candidate -- one member of a candidate population.

A `Candidate` is the DATA record of a design variation competing under a genome (FunSearch-
style small population; Romera-Paredes et al., 2024). It carries identity, lineage, and the
strategy it embodies -- never the live callable, so it stays frozen and serializable. The
bake-off pairs each Candidate with its implementation at run time and fills in the disposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The disposition ladder for a scored candidate. A candidate is NEVER auto-promoted past
# `qualified`; promotion to `elite` is a human decision (Human Keel Doctrine).
CANDIDATE_STATUSES = (
    "generated",
    "rejected",  # failed a hard gate
    "qualified",  # passed hard gates; eligible, pending human choice
    "elite",  # the human-approved baseline (set only by Josh)
    "quarantined",
    "archived",
)


@dataclass(frozen=True)
class Candidate:
    """One design variation: who it is, where it came from, and the strategy it embodies."""

    candidate_id: str
    genome_id: str
    strategy: str  # e.g. "minimal" | "performance" | "extensibility"
    impl_name: str  # the callable's name, for provenance (the callable is passed separately)
    lineage: tuple[str, ...] = field(default_factory=tuple)  # ancestry, e.g. ("elite_baseline",)
    disposition: str = "generated"

    def with_disposition(self, disposition: str) -> Candidate:
        """Return a copy with a new disposition (frozen -> a new record, never a mutation)."""
        if disposition not in CANDIDATE_STATUSES:
            raise ValueError(f"unknown disposition {disposition!r}; use {CANDIDATE_STATUSES}")
        return Candidate(
            candidate_id=self.candidate_id,
            genome_id=self.genome_id,
            strategy=self.strategy,
            impl_name=self.impl_name,
            lineage=self.lineage,
            disposition=disposition,
        )
