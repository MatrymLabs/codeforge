"""CARD: callings -- the gate between a character and a calling they have not yet earned.

A seed may declare that a calling is advanced: it opens only to someone who has already walked
other paths far enough. Before this card, every calling in every seed was choosable at level one,
including the ones the world bible describes as the end of a long road.

The rule lives in the DATA, not here. A calling declares what it wants:

    warden:
      name: Warden
      requires: {vanguard: 5, pathfinder: 3}

and this card only reads that against what the character has actually earned. `requires` is
optional, so a foundational calling omits it and stays open to anyone, which is why adding this
card locked nothing that was previously open until a seed asked for it.

Inputs:  a calling label, its Job record, and the character's job_progress (label -> JobProgress).
Outputs: a CallingVerdict naming every unmet requirement, never a bare boolean. A refusal that
         cannot say what is missing is a wall, not a gate, and the player is owed the road.

Derive, don't store: standing is read from the JobProgress records the world already keeps, so a
character who levels a prerequisite calling unlocks the advanced one with no migration and no new
persisted field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CallingVerdict",
    "Requirement",
    "gate_calling",
    "prerequisite_cycles",
    "requirements_of",
]


@dataclass(frozen=True)
class Requirement:
    """One thing a calling asks for: a prior calling, carried to at least this level."""

    calling: str
    level: int

    def phrase(self, name: str | None = None) -> str:
        """How this requirement reads to a player. `name` is the calling's display name."""
        shown = name or self.calling
        return f"{shown} at level {self.level}"


@dataclass(frozen=True)
class CallingVerdict:
    """Whether a calling is open, and if not, exactly what is still missing.

    A verdict rather than a boolean, so the caller cannot accidentally render "no" as silence.
    """

    calling: str
    unmet: tuple[Requirement, ...] = ()

    @property
    def open(self) -> bool:
        """True when nothing stands in the way."""
        return not self.unmet

    def reason(self, names: Mapping[str, str] | None = None) -> str:
        """Why the calling is closed, in the player's language. Empty when it is open."""
        if self.open:
            return ""
        lookup = names or {}
        missing = ", ".join(r.phrase(lookup.get(r.calling)) for r in self.unmet)
        return f"That path is not yet open to you. It asks for {missing}."


def requirements_of(job: Mapping[str, Any]) -> tuple[Requirement, ...]:
    """The requirements a Job declares, in a stable order so output never shuffles."""
    declared = job.get("requires") or {}
    return tuple(
        Requirement(calling=label, level=int(level)) for label, level in sorted(declared.items())
    )


def gate_calling(
    label: str,
    job: Mapping[str, Any],
    held: Mapping[str, Any],
) -> CallingVerdict:
    """Weigh one calling against what this character has actually earned.

    `held` maps a calling label to anything carrying a `job_level` (a JobProgress). A calling the
    character has never touched counts as level 0, not level 1: opening a record by taking a job
    for one moment must not satisfy a requirement that asks for the road.
    """
    unmet = tuple(
        need for need in requirements_of(job) if _standing(held.get(need.calling)) < need.level
    )
    return CallingVerdict(calling=label, unmet=unmet)


def _standing(record: Any) -> int:
    """A character's level in one calling. Absent record means never walked, which is 0."""
    if record is None:
        return 0
    level = getattr(record, "job_level", 0)
    return level if isinstance(level, int) and not isinstance(level, bool) else 0


def prerequisite_cycles(jobs: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, ...]]:
    """Every cycle in the prerequisite graph, so a seed cannot ship an unreachable calling.

    A calling that requires itself, or two that require each other, can never be taken by anyone.
    That is a content bug the loader should refuse at startup rather than a mystery a player
    discovers by failing forever. Returns each cycle once, as the path that closes it.
    """
    cycles: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    visiting: dict[str, int] = {}
    trail: list[str] = []

    def walk(label: str) -> None:
        if label in visiting:
            cycle = tuple(trail[visiting[label] :])
            key = _canonical(cycle)
            if key not in seen:
                seen.add(key)
                cycles.append(cycle)
            return
        if label not in jobs:
            return  # a dangling reference is a different complaint; the loader names it separately
        visiting[label] = len(trail)
        trail.append(label)
        for need in requirements_of(jobs[label]):
            walk(need.calling)
        trail.pop()
        del visiting[label]

    for label in sorted(jobs):
        walk(label)
    return cycles


def _canonical(cycle: tuple[str, ...]) -> tuple[str, ...]:
    """A rotation-independent key, so A->B->A and B->A->B are recorded as one cycle."""
    if not cycle:
        return cycle
    pivot = cycle.index(min(cycle))
    return cycle[pivot:] + cycle[:pivot]
