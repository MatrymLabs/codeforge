"""CARD: release_gate -- the practical adapter for test evidence: a release-readiness gate.

The reverse of parts/world_cert: the SAME `EvidenceLedger` core gates a software release. It expects
evidence for the release checks (lint, tests, coverage, security) and is ready only when every one
has PASSED evidence -- a check with no evidence (a step that never ran) can never be reported ready.
Its cousins are CI gates, regression sign-off, and release checklists.
"""

from __future__ import annotations

from parts.test_evidence import EvidenceLedger

_REQUIRED = ("lint", "tests", "coverage", "security")


class ReleaseGate:
    """A release readiness gate: record CI check evidence; ready only when all required pass."""

    def __init__(self, commit: str = "", environment: str = "ci") -> None:
        self._ledger = EvidenceLedger(environment=environment, commit=commit)
        for check in _REQUIRED:
            self._ledger.expect(check)

    def record(self, check: str, status: str, detail: str = "") -> None:
        self._ledger.record(check, status, detail)

    def is_ready(self) -> bool:
        """True only when every required check has PASSED evidence."""
        return self._ledger.passed()

    def gaps(self) -> list[str]:
        """The check ids that are not passed (missing, failed, error)."""
        return [e.check_id for e in self._ledger.gaps()]

    def report(self) -> str:
        return self._ledger.report()
