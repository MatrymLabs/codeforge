"""CARD: completeness -- report which required categories a tagged collection covers, and the gaps.

The recurring content-QA question, in one honest instrument: given a collection where each thing
carries a category tag (gear by equip slot, spells by school, controls by family) and the set of
categories that MUST be present, which are covered, which are MISSING, and which are extra? It is
the "system measures" half of build-and-measure: author content, then ask where the gaps are,
region by region, before calling a thing complete. Pure and stdlib-only; it owns no data source --
the caller extracts the tags and hands them in.

    coverage(["head", "body", "head"], required=["head", "body", "arm"])
    # -> Coverage(covered={head, body}, missing={arm}, extra=set()); .complete is False

One mechanism, many jobs:
- game: does each Reach drop every equip slot; does a class cover every spell school; does a
  dungeon span every planned encounter type.
- general: any "at least one per required category" completeness check with an honest gap list
  (feature-flag audits, translation-key coverage, capability matrices).
- records: does a system security plan address every required control family; which are unaddressed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


class CoverageError(ValueError):
    """No required categories: a completeness check against an empty requirement is meaningless --
    fail loud rather than report a vacuous pass."""


@dataclass(frozen=True)
class Coverage:
    """The verdict of a completeness check: the required categories that are present (`covered`),
    the required ones absent (`missing`), and the present-but-not-required (`extra`). `complete` is
    the headline: nothing required is missing."""

    covered: frozenset[str]
    missing: frozenset[str]
    extra: frozenset[str]

    @property
    def complete(self) -> bool:
        """True when every required category is present (no gaps)."""
        return not self.missing


def coverage(present: Iterable[str], required: Iterable[str]) -> Coverage:
    """Report how a tagged collection's present categories cover a required set. `present` is the
    categories actually found (duplicates collapse; order does not matter); `required` is the set
    that must all appear. Fails loud on an empty `required` -- completeness against no requirement
    is a meaningless pass."""
    required_set = frozenset(required)
    if not required_set:
        raise CoverageError("completeness needs at least one required category")
    present_set = frozenset(present)
    return Coverage(
        covered=required_set & present_set,
        missing=required_set - present_set,
        extra=present_set - required_set,
    )
