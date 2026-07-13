"""CARD: patch_tracker -- the practical adapter for the change ledger: a software patch tracker.

The reverse of parts/maintenance: the SAME `ChangeLedger` core tracks real software patches -- a
dependency bump or a CVE fix -- through the gated lifecycle, with the promotion gate that a patch
may not reach canary until its tests pass. Its cousins are dependency-update trackers, release
trains, and any governed software-change record.
"""

from __future__ import annotations

from parts.change_ledger import Change, ChangeLedger


class PatchTracker:
    """Track software patches through the gated lifecycle (record -> approve -> ... -> close)."""

    def __init__(self) -> None:
        self._ledger = ChangeLedger()

    def record_cve_patch(
        self,
        patch_id: str,
        title: str,
        severity: str,
        cve: str,
        component: str,
        rollback_plan: str = "",
    ) -> Change:
        """Record a security patch that fixes a CVE in a component."""
        return self._ledger.open(
            patch_id,
            title,
            "security",
            severity,
            "ci",
            cve_refs=(cve,),
            components=(component,),
            rollback_plan=rollback_plan,
        )

    def record_dependency_bump(self, patch_id: str, title: str, component: str) -> Change:
        """Record a routine dependency update."""
        return self._ledger.open(
            patch_id, title, "dependency", "low", "ci", components=(component,)
        )

    def pass_tests(self, patch_id: str, check: str = "ci") -> None:
        """Record passing test evidence (the gate the promotion to canary reads)."""
        self._ledger.record_test(patch_id, check)

    def review_arc(self, patch_id: str, verdict: str = "watchlist") -> None:
        """Record the ARC readiness verdict (the gate the promotion to deploy reads)."""
        self._ledger.record_arc(patch_id, verdict)

    def advance(self, patch_id: str, event: str, actor: str = "*"):
        return self._ledger.advance(patch_id, event, actor=actor)

    def status(self, patch_id: str) -> str:
        return self._ledger.status(patch_id)

    def history(self, patch_id: str) -> list[dict[str, str]]:
        return self._ledger.history(patch_id)

    def arc_status(self) -> tuple[str, str]:
        """The patch dimension's ARC verdict, from the same change core, with a patch citation."""
        status, detail = self._ledger.arc_status()
        return (status, f"patch_tracker: {detail}")
