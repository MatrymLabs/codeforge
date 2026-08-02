"""CARD: evolution.counterexamples -- failures become permanent regression knowledge.

Counterexample-driven search (Helmuth et al., 2024): every discovered failure is normalized
to a signature, deduplicated, and kept, so a defect a candidate hits once becomes part of the
fitness landscape for every future candidate. This is how the lab improves through experience
without pretending a model "learned" anything mystical.

v1: an in-memory + JSON-serializable bank with normalization and dedup. Regression-test
generation and Classroom-lesson export are later slices; the bank already records everything
those will need.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Statuses from the report. v1 uses `new` and `duplicate`; the rest are for later slices.
COUNTEREXAMPLE_STATUSES = (
    "new",
    "normalized",
    "duplicate",
    "regression_created",
    "resolved",
    "false_positive",
    "archived",
)

_NUM = re.compile(r"\d+")


@dataclass(frozen=True)
class Counterexample:
    """One reproducible failure: what broke, what was expected, and its normalized signature."""

    signature: str  # normalized fingerprint (numbers/quotes flattened) -> dedup key
    affected: str  # the subsystem / genome under test
    failing_input: str  # the exact input that failed (human-readable)
    expected: str
    actual: str
    first_seen: str  # the candidate id that first hit it
    occurrences: int = 1
    status: str = "new"


def normalize_signature(affected: str, detail: str) -> str:
    """A stable fingerprint: lowercase, digits flattened to N, quotes stripped. Two failures
    that differ only in a literal value share one signature (so they dedup)."""
    flattened = _NUM.sub("N", detail.lower())
    flattened = flattened.replace("'", "").replace('"', "")
    return f"{affected}:{flattened.strip()}"


class CounterexampleBank:
    """A governed store of failures: add normalizes + dedups; nothing grows unbounded silently."""

    def __init__(self) -> None:
        self._by_signature: dict[str, Counterexample] = {}

    def add(
        self, affected: str, failing_input: str, expected: str, actual: str, candidate_id: str
    ) -> Counterexample:
        """Record a failure. A repeat of a known signature bumps its count, not a new row."""
        signature = normalize_signature(affected, f"{failing_input}->{actual}")
        existing = self._by_signature.get(signature)
        if existing is not None:
            bumped = Counterexample(
                signature=existing.signature,
                affected=existing.affected,
                failing_input=existing.failing_input,
                expected=existing.expected,
                actual=existing.actual,
                first_seen=existing.first_seen,
                occurrences=existing.occurrences + 1,
                status="duplicate",
            )
            self._by_signature[signature] = bumped
            return bumped
        fresh = Counterexample(
            signature=signature,
            affected=affected,
            failing_input=failing_input,
            expected=expected,
            actual=actual,
            first_seen=candidate_id,
        )
        self._by_signature[signature] = fresh
        return fresh

    def all(self) -> list[Counterexample]:
        """Every stored counterexample, sorted by signature (deterministic)."""
        return [self._by_signature[k] for k in sorted(self._by_signature)]

    def to_dicts(self) -> list[dict[str, Any]]:
        """JSON-ready records (for a report or an evidence file)."""
        return [
            {
                "signature": c.signature,
                "affected": c.affected,
                "failing_input": c.failing_input,
                "expected": c.expected,
                "actual": c.actual,
                "first_seen": c.first_seen,
                "occurrences": c.occurrences,
                "status": c.status,
            }
            for c in self.all()
        ]

    def __len__(self) -> int:
        return len(self._by_signature)
