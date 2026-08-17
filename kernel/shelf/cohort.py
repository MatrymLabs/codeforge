"""CARD: cohort -- a transient membership group: a leader-led band, formed, joined, left, disbanded.

The reusable core behind a party (and the shape a guild, a chat room, a work group, or a raid all
share): a small ORDERED group of member ids with a leader (the head of the list), plus a registry
that keeps a member->group map so any member can reach their group in one lookup. Membership is the
whole responsibility: forming a group, admitting a member (bounded by a max size), leaving with
automatic leadership handoff, and disbanding. It carries no domain: no chat, no combat, no
rewards, no persistence. A caller layers those on top (the game's party bolts invites + broadcast +
logout cleanup onto this core).

Framework-free and fail-loud: adding a member already grouped, or to a full group, raises rather
than silently corrupting the member->group map (the invariant that keeps two groups from claiming
one member). Leaving hands leadership to the next member and disbands an emptied group, so the
registry never keeps a ghost.

Provenance: independently_implemented_pattern (transient membership group), harvested from the
game's party/trade/loot systems. No code copied.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class CohortError(ValueError):
    """A membership rule was broken (already grouped, or full): fail loud, never corrupt the map."""


@dataclass
class Cohort:
    """One group: an ORDERED list of member ids whose head is the leader. Leadership handoff is just
    dropping the leaver and promoting the new head; no separate leader field to drift."""

    members: list[str] = field(default_factory=list)

    @property
    def leader(self) -> str:
        return self.members[0] if self.members else ""

    def __contains__(self, member: str) -> bool:
        return member in self.members

    def __len__(self) -> int:
        return len(self.members)


class CohortRegistry:
    """The member->group map for a family of cohorts, bounded by a per-group `max_size`. One
    registry owns one kind of group (all parties, or all guilds); a member belongs to at most one
    group in it, and the map is the single source of truth for who is grouped with whom."""

    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise CohortError(f"max_size must be at least 1, got {max_size}")  # noqa: TRY003
        self.max_size = max_size
        self._of: dict[str, Cohort] = {}

    def cohort_of(self, member: str) -> Cohort | None:
        """The group a member belongs to, or None if they are ungrouped."""
        return self._of.get(member)

    def clear(self) -> None:
        """Drop every group (a reset for a fresh world, or between tests)."""
        self._of.clear()

    def is_full(self, cohort: Cohort) -> bool:
        return len(cohort.members) >= self.max_size

    def form(self, leader: str) -> Cohort:
        """Start a new group with `leader` as its sole (and leading) member. Raises if that member
        is already in a group (leave it first)."""
        if leader in self._of:
            raise CohortError(f"{leader!r} is already in a group")  # noqa: TRY003
        cohort = Cohort([leader])
        self._of[leader] = cohort
        return cohort

    def add(self, cohort: Cohort, member: str) -> None:
        """Admit `member` to `cohort`. Raises if they are already grouped or the group is full."""
        if member in self._of:
            raise CohortError(f"{member!r} is already in a group")  # noqa: TRY003
        if self.is_full(cohort):
            raise CohortError(f"the group is full ({self.max_size})")  # noqa: TRY003
        cohort.members.append(member)
        self._of[member] = cohort

    def leave(self, member: str) -> tuple[Cohort | None, bool]:
        """Remove `member` from their group. Returns (group_after, was_leader): `group_after` is the
        group with the member gone (a new leader promoted if they led it), or None if that emptied
        and disbanded the group. A no-op returns (None, False) for an ungrouped member."""
        cohort = self._of.get(member)
        if cohort is None:
            return (None, False)
        was_leader = cohort.leader == member
        cohort.members.remove(member)
        self._of.pop(member, None)
        if not cohort.members:
            return (None, was_leader)  # the last member left: the group is gone
        return (cohort, was_leader)

    def disband(self, cohort: Cohort) -> list[str]:
        """Dissolve a whole group. Returns its former members (for the caller to notify) and clears
        the map for each, so the registry holds no ghost."""
        members = list(cohort.members)
        for member in members:
            self._of.pop(member, None)
        cohort.members.clear()
        return members
