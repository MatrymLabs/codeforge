"""CARD: stewardship.change -- the ChangeDescriptor: the assurance-relevant facts of one change.

The Stewardship Gate never re-scans; it READS a change's already-computed signals (tests, SAST,
secrets, dependency admission, AI disclosure) as typed data. That way the gate composes the
existing controls (`make check` / `security` / `deps`) instead of duplicating them -- avoiding
the alert-fatigue waste the FWA report warns against. A caller populates this from PR/CI metadata.

`ai_assisted = None` is meaningful: it means UNDISCLOSED, which the gate treats as a traceability
failure. Disclosure must be an explicit True or False.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangeDescriptor:
    """One proposed change, as the facts an assurance gate needs -- not the diff itself."""

    change_id: str
    title: str
    files_touched: tuple[str, ...] = field(default_factory=tuple)
    ai_assisted: bool | None = None  # None = UNDISCLOSED (a traceability failure)
    tests_passed: bool = False
    sast_blocking_findings: int = 0  # blocking bandit/SAST findings (from `make security`)
    secrets_findings: int = 0  # detect-secrets hits (from `make secrets`)
    dependencies_added: tuple[str, ...] = field(default_factory=tuple)
    dependencies_approved: bool = True  # every added dep admitted (ledger / DependencyGate)
    human_approvals: int = 0  # count of human review approvals on the change
