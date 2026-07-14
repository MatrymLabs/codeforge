"""CARD: arc_ledger -- file and read the runtime dimensions' verdicts as dated evidence.

ARC (parts/arc.py) composes ten review dimensions. Six read filed evidence directly; the four
runtime ones (change, patch, evidence, release) have no verdict on disk until their gate runs. This
is the seam that lets a gate FILE its verdict (a dated JSON under `arc-evidence/`, git-ignored and
reproducible from the recorded commit, exactly like `security-evidence/`) and lets ARC READ the
latest one, read-only. Two rules keep it honest: absence of a filed verdict is MISSING, never a
pass (ARC's load-bearing rule); and a malformed artifact fails loud (VerdictError) rather than
rendering a false verdict.

`emit()` is the driver behind `make arc-verdicts`: it runs the release checks through the
allowlisted console runner (a seam, injected in tests so they never touch a subprocess), maps the
real outcomes to release/evidence verdicts, and files them. change/patch have no persistent store
yet, so they stay MISSING by absence (a later slice adds the store); nothing here fabricates state.

Provenance: original composition of CodeForge parts (test_evidence, console). No code copied.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from parts.verdicts import ARC_STATUSES as _STATUSES

# The four runtime dimensions ARC reads through this ledger; statuses come from verdicts.py (the
# one home for the ARC readiness tier), so this module and arc.py can never drift apart.
RUNTIME_DIMENSIONS = ("change", "patch", "evidence", "release")
ARC_EVIDENCE_DIR = "arc-evidence"  # git-ignored, dated, reproducible (mirrors security-evidence/)


class VerdictError(ValueError):
    """A malformed or unreadable verdict artifact: fail loud, never render a false pass."""


@dataclass(frozen=True)
class Verdict:
    """One runtime dimension's filed verdict, and the gate/commit it was computed from."""

    dimension: str
    status: str
    source: str  # a citation; a verdict must always name where it came from
    commit: str  # the short sha the verdict was computed at (reproducibility)
    recorded_utc: str  # ISO-8601 stamp


def _evidence_dir(root: Path | None) -> Path:
    base = root if root is not None else Path(__file__).resolve().parent.parent
    return base / ARC_EVIDENCE_DIR


def record_verdict(
    dimension: str,
    status: str,
    source: str,
    *,
    commit: str,
    root: Path | None = None,
    stamp: datetime | None = None,
) -> Path:
    """File one dated verdict JSON, return its path. Validates like ARC's Dimension: fails loud."""
    if dimension not in RUNTIME_DIMENSIONS:
        raise VerdictError(
            f"unknown runtime dimension {dimension!r}; expected {RUNTIME_DIMENSIONS}"
        )
    if status not in _STATUSES:
        raise VerdictError(
            f"dimension {dimension!r}: status must be one of {_STATUSES}, got {status!r}"
        )
    if not source.strip():
        raise VerdictError(f"dimension {dimension!r}: a verdict must cite its source")
    when = stamp if stamp is not None else datetime.now(UTC)
    verdict = Verdict(
        dimension=dimension,
        status=status,
        source=source,
        commit=commit or "unknown",
        recorded_utc=when.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    directory = _evidence_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    # ISO date prefix sorts lexicographically, so read_latest() = max(); a same-day rerun overwrites
    # the file rather than accreting duplicates.
    path = directory / f"{when.strftime('%Y-%m-%d')}-{dimension}.json"
    path.write_text(json.dumps(verdict.__dict__, indent=2) + "\n", encoding="utf-8")
    return path


def read_latest(dimension: str, root: Path | None = None) -> Verdict | None:
    """The newest filed Verdict for a dimension, or None if none is filed (then it is MISSING).

    A malformed or partial artifact raises VerdictError: a dishonest verdict is worse than an error.
    """
    directory = _evidence_dir(root)
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob(f"*-{dimension}.json"))
    if not candidates:
        return None
    newest = candidates[-1]
    try:
        raw = json.loads(newest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise VerdictError(f"{newest.name}: unreadable verdict artifact ({exc})") from exc
    try:
        verdict = Verdict(
            dimension=raw["dimension"],
            status=raw["status"],
            source=raw["source"],
            commit=raw["commit"],
            recorded_utc=raw["recorded_utc"],
        )
    except (KeyError, TypeError) as exc:
        raise VerdictError(f"{newest.name}: malformed verdict artifact (missing {exc})") from exc
    if verdict.status not in _STATUSES:
        raise VerdictError(f"{newest.name}: unknown status {verdict.status!r}")
    if not verdict.source.strip():
        raise VerdictError(f"{newest.name}: a verdict must cite its source")
    return verdict


# --- the driver: file the release + evidence verdicts from real check outcomes -----------------

# The release checks, mapped to the real commands that establish each. A private allowlist passed to
# console.run(), so console's own ALLOWLIST is untouched. The `coverage` run IS the full suite, so
# it honestly establishes both `tests` and `coverage` in one pass (no double suite run).
_CHECK_CMDS: dict[str, list[str]] = {
    "lint": ["ruff", "check", "."],
    "coverage": [
        "pytest",
        "-n",
        "auto",
        "--cov=parts",
        "--cov=forge",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-fail-under=85",
    ],
    "security": ["bandit", "-c", "pyproject.toml", "-r", "parts", "forge.py", "-q"],
}


def _console_runner(check: str) -> bool:
    """Default runner: run one allowlisted check via the safe console runner; True iff it passed."""
    from parts import console  # lazy: keep this module's import path light for arc.py

    return console.run(check, allowlist=_CHECK_CMDS).ok


def emit(commit: str, *, root: Path | None = None, runner=None) -> list[Path]:
    """Run the release checks and file the runtime verdicts: release as a dated arc-evidence/
    verdict, evidence as a retained Chronicle record (slice 1b). Returns the arc-evidence/ paths.

    `runner(check) -> bool` is a seam (default: the console runner); tests inject a fake so they
    never touch a subprocess. change/patch have no persistent store yet, so they are NOT filed here
    and stay MISSING by absence (honest, not fabricated).
    """
    from parts.release_gate import ReleaseGate
    from parts.test_evidence import FAILED, PASSED, EvidenceLedger

    run_check = runner if runner is not None else _console_runner
    lint_ok = run_check("lint")
    cov_ok = run_check("coverage")  # the full suite: establishes both `tests` and `coverage`
    security_ok = run_check("security")
    outcomes = {"lint": lint_ok, "tests": cov_ok, "coverage": cov_ok, "security": security_ok}

    gate = ReleaseGate(commit=commit)
    for check in ("lint", "tests", "coverage", "security"):
        gate.record(check, PASSED if outcomes[check] else FAILED)

    evidence = EvidenceLedger(commit=commit)
    for check in ("tests", "coverage"):
        evidence.expect(check)
        evidence.record(check, PASSED if outcomes[check] else FAILED)

    rel_status, rel_source = gate.arc_status()
    ev_status, ev_detail = evidence.arc_status()
    # Release stays a dated verdict under arc-evidence/ (git-ignored, reproducible). Evidence now
    # lives SOLELY in the Chronicle (git-tracked, hash-chained), which ARC reads back (slice 1b) -
    # a single retained source, not a git-ignored one.
    from parts import chronicle

    filed = [record_verdict("release", rel_status, rel_source, commit=commit, root=root)]
    chronicle.append(
        "evidence",
        {"status": ev_status, "source": f"test_evidence: {ev_detail}", "dimension": "evidence"},
        commit=commit,
        root=root,
    )
    # Record the provenance of this gate run (slice 3): the evidence was generated by the run at
    # this commit, and the release verdict was informed by that evidence.
    chronicle.record_edge(
        f"evidence:{commit}", "wasGeneratedBy", f"gate-run:{commit}", commit=commit, root=root
    )
    chronicle.record_edge(
        f"release:{commit}", "wasInformedBy", f"evidence:{commit}", commit=commit, root=root
    )
    return filed


def main(argv: list[str] | None = None) -> int:
    """`python -m parts.arc_ledger emit <commit>`: file the runtime verdicts (human-run)."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "emit":
        print("usage: python -m parts.arc_ledger emit <commit>")
        return 2
    commit = args[1] if len(args) > 1 else "unknown"
    for path in emit(commit):
        print(f"  filed {path.name}")
    print("  evidence -> retained in the Chronicle (chronicle/ledger.jsonl)")
    print("change + patch: no persistent store yet -> honestly MISSING (a later slice adds it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
