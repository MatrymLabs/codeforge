"""CARD: test_evidence -- record check evidence honestly: missing evidence is never a pass.

Declare the checks you require, record each one's outcome (with the environment and commit it ran
under), and ask whether everything passed. The load-bearing rules: an expected check with no record
is MISSING (not a pass), a runner ERROR is distinct from a test FAILED, and `passed()` is true only
when every check is PASSED. This is the standard test-evidence / quality-gate idea, reimplemented
from the concept -- no code copied.

Framework-free and side-effect-free: it stores what you record, nothing more. One core, two lives: a
world-readiness certificate in the game (`parts/world_cert`) and a release-readiness gate in a
practical app (`parts/release_gate`).

Provenance: independently_implemented_pattern (test evidence / quality gate). No code copied.
"""

from __future__ import annotations

from dataclasses import dataclass

PASSED, FAILED, ERROR, SKIPPED, MISSING = "passed", "failed", "error", "skipped", "missing"
# ERROR is the runner/harness failing (distinct from a check that ran and FAILED).
_RECORDABLE = (PASSED, FAILED, ERROR, SKIPPED)


class EvidenceError(ValueError):
    """An invalid status was recorded. Fails loud."""


@dataclass(frozen=True)
class Evidence:
    """One check's evidence: its id, status, the environment and commit it ran under, a detail."""

    check_id: str
    status: str
    environment: str = ""
    commit: str = ""
    detail: str = ""


class EvidenceLedger:
    """Collect check evidence and answer whether everything passed, never faking a missing pass."""

    def __init__(self, environment: str = "", commit: str = "") -> None:
        self._env = environment
        self._commit = commit
        self._records: dict[str, Evidence] = {}
        self._expected: set[str] = set()

    def expect(self, check_id: str) -> None:
        """Declare a check that MUST have evidence; without it, the check is MISSING."""
        self._expected.add(check_id)

    def record(self, check_id: str, status: str, detail: str = "") -> None:
        """Record a check's outcome. Raises EvidenceError on an unrecordable status."""
        if status not in _RECORDABLE:
            raise EvidenceError(f"cannot record status {status!r}; use one of {_RECORDABLE}")
        self._records[check_id] = Evidence(check_id, status, self._env, self._commit, detail)

    def results(self) -> list[Evidence]:
        """Every check's evidence; an expected-but-unrecorded check appears as MISSING."""
        ids = sorted(self._expected | set(self._records))
        return [
            self._records.get(cid, Evidence(cid, MISSING, self._env, self._commit, "no evidence"))
            for cid in ids
        ]

    def passed(self) -> bool:
        """True only if there is at least one check and every one PASSED (missing/error is not)."""
        results = self.results()
        return bool(results) and all(r.status == PASSED for r in results)

    def gaps(self) -> list[Evidence]:
        """Every check that is not PASSED (missing, failed, error, skipped)."""
        return [r for r in self.results() if r.status != PASSED]

    def report(self) -> str:
        """A readable evidence report: overall verdict and each check."""
        verdict = "PASS" if self.passed() else "NOT PASSED"
        lines = [f"EVIDENCE: {verdict}  (commit {self._commit or '?'} / env {self._env or '?'})"]
        for r in self.results():
            suffix = f"  ({r.detail})" if r.detail else ""
            lines.append(f"  [{r.status:<7}] {r.check_id}{suffix}")
        return "\n".join(lines)

    def arc_status(self) -> tuple[str, str]:
        """Map this ledger's evidence to an ARC status (ready|watchlist|blocked|missing) + a detail.

        Honest by construction: no evidence at all is MISSING (never a pass); a check that ran and
        FAILED or ERRORed blocks; a soft gap (expected-but-unrun / skipped) holds the watchlist;
        only all-PASSED is ready. ARC reads a filed copy of this; it never runs the checks itself.
        """
        results = self.results()
        if not results:
            return ("missing", "no checks recorded")
        if self.passed():
            return ("ready", f"{len(results)} checks, all passed")
        gap_statuses = {g.status for g in self.gaps()}
        status = "blocked" if (FAILED in gap_statuses or ERROR in gap_statuses) else "watchlist"
        return (status, f"{len(results)} checks, {len(self.gaps())} gap(s)")
