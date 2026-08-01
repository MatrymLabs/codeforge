"""CARD: checklist_gate -- require a signed pre-flight attestation before an irreversible action.

Clean-room from the Clinical Workflow research (the WHO surgical sign-in / time-out
/ sign-out gates transferred to coding, RS-2026-07-11-clinical p.5-6). Before an
irreversible action (a deploy, a migration, an autonomous change), a phase-keyed
checklist must be attested: repository context, runtime target, secret exposure,
test coverage, rollback plan, and whether the action is authorized. An unattested
required item BLOCKS the action and names exactly what is missing, so a critical
step is never skipped silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class ChecklistError(ValueError):
    """Raised when a checklist is declared malformed."""


class GateBlocked(Exception):
    """Raised when required attestations are missing or unchecked (the gate holds)."""

    def __init__(self, phase: str, failures: tuple[str, ...]) -> None:
        self.phase = phase
        self.failures = failures
        super().__init__(f"{phase} gate blocked; unattested: {', '.join(failures)}")


@dataclass(frozen=True)
class Item:
    """One thing that must be confirmed before the action proceeds."""

    key: str
    prompt: str
    required: bool = True

    def __post_init__(self) -> None:
        if not self.key:
            raise ChecklistError("item key must be non-empty")


@dataclass(frozen=True)
class Checklist:
    """A phase-keyed set of pre-flight items (sign-in / time-out / sign-out)."""

    phase: str
    items: tuple[Item, ...]

    def __post_init__(self) -> None:
        if not self.phase:
            raise ChecklistError("checklist phase must be non-empty")
        if not self.items:
            raise ChecklistError("a checklist needs at least one item")
        keys = [i.key for i in self.items]
        if len(keys) != len(set(keys)):
            raise ChecklistError("checklist item keys must be unique")


def verify(checklist: Checklist, attestations: Mapping[str, bool], *, actor: str = "") -> None:
    """Raise GateBlocked unless every REQUIRED item is attested True.

    An optional item may be absent. An unknown attestation key is ignored (the
    checklist is authoritative). Passes silently when the gate is satisfied.
    """
    if not isinstance(attestations, Mapping):
        raise ChecklistError("attestations must be a mapping of item key -> bool")
    failures: list[str] = []
    for item in checklist.items:
        if not item.required:
            continue
        if attestations.get(item.key) is not True:
            failures.append(item.key)
    if failures:
        raise GateBlocked(checklist.phase, tuple(failures))


def missing(checklist: Checklist, attestations: Mapping[str, bool]) -> tuple[str, ...]:
    """The required item keys not yet attested (empty = ready). Non-raising."""
    return tuple(
        i.key for i in checklist.items if i.required and attestations.get(i.key) is not True
    )


def time_out() -> Checklist:
    """The canonical pre-action 'time-out' gate for an irreversible coding action."""
    return Checklist(
        "time-out",
        (
            Item("repo_context", "repository, branch, and service confirmed"),
            Item("runtime_target", "runtime / environment target confirmed"),
            Item("secrets_exposure", "no secret is exposed or logged by this change"),
            Item("test_coverage", "the affected path is covered by tests that ran green"),
            Item("rollback_plan", "a tested rollback path exists"),
            Item("authorized", "this action is authorized (not advisory-only)"),
            Item("dependency_review", "any new dependency was admitted", required=False),
        ),
    )
