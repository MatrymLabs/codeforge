"""CARD: arc -- ARC (Assurance, Readiness, Control): compose gate verdicts into one honest report.

CodeForge's umbrella engineering-review system, the coherent Blueprint filed as `arc`. ARC adds
NO new gate: it READS the verdicts of the review dimensions CodeForge already has and composes
them into one honest overall verdict (ready | watchlist | blocked). Two load-bearing rules keep it
truthful: a dimension whose gate has not been wired or has never run is MISSING, and MISSING is
never a pass; and every dimension cites the source its status came from, never an invented one.

The **Control** axis is read from the Chronicle (the ship's memory): an open high/critical incident
or a regressed ai-eval holds the verdict at WATCHLIST. That makes the incident/ai-eval records
load-bearing on readiness, not a store nothing reads (a tampered Chronicle fails loud on read).

Nine dimensions read real FILED evidence. Six read the repo directly (ADRs, CI + tests, pattern
docs, the dependency ledger, benchmarks, security evidence). Two runtime gates (release, evidence)
file a dated verdict (release via parts/arc_ledger, evidence via the Chronicle) when
`make arc-verdicts` runs their checks; ARC reads the latest, read-only. Control reads the Chronicle
(incidents + ai-eval regressions). The last two (change, patch) have no persistent store yet, so
they stay MISSING - honestly, never faked (a later slice adds the store). Absence of a filed verdict
is always MISSING, never a pass. ARC reads only: it opens no gate and runs no check as a side effect
(architecture law 1). The world is the interface; `arc` is the room's window.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from parts import arc_ledger

if TYPE_CHECKING:
    from parts.chronicle import Record

# Per-dimension status, from the one shared home (verdicts.py); re-exported so callers/tests can
# still `from parts.arc import READY, ...`. MISSING = no wired source / never ran: never a pass.
from parts.verdicts import ARC_STATUSES as _DIM_STATUSES
from parts.verdicts import BLOCKED, MISSING, READY, WATCHLIST

# The review dimensions ARC composes: the ten assurance/readiness gates, plus the Control axis
# read from the Chronicle (incidents + ai-eval regressions).
DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("architecture", "ADRs + frameup"),
    ("testing", "qualitygate / make check"),
    ("documentation", "integrity ritual + CARD checks"),
    ("dependency", "make deps + dependency_ledger.toml"),
    ("performance", "performance gate + benchmarks/"),
    ("security", "make security + security-evidence/"),
    ("change", "change_ledger"),
    ("patch", "patch_tracker + make patch"),
    ("evidence", "test_evidence / EvidenceLedger"),
    ("release", "release_gate / make readiness"),
    ("control", "chronicle: open incidents + ai-eval regressions"),
)


class ArcError(ValueError):
    """A malformed ARC dimension: fail loud rather than render a dishonest verdict."""


@dataclass(frozen=True)
class Dimension:
    """One review dimension's verdict, and the gate/artifact the verdict came from."""

    name: str
    status: str
    source: str  # a citation; a status must always name where it came from

    def __post_init__(self) -> None:
        if self.status not in _DIM_STATUSES:
            raise ArcError(
                f"dimension {self.name!r}: status must be one of {_DIM_STATUSES}, "
                f"got {self.status!r}"
            )
        if not self.source.strip():
            raise ArcError(f"dimension {self.name!r}: a status must cite its source")


@dataclass(frozen=True)
class ArcReport:
    """The composed verdict over all reviewed dimensions."""

    dimensions: tuple[Dimension, ...]
    verdict: str


def compose(dimensions: list[Dimension] | tuple[Dimension, ...]) -> ArcReport:
    """Compose per-dimension verdicts into one overall verdict. Fails loud on an empty review.

    The rule (honest, not lenient): any BLOCKED dimension blocks the whole report; otherwise any
    WATCHLIST or MISSING dimension keeps it on the watchlist; only an all-READY review is READY.
    """
    dims = tuple(dimensions)
    if not dims:
        raise ArcError("ARC needs at least one dimension to review")
    statuses = {d.status for d in dims}
    if BLOCKED in statuses:
        verdict = BLOCKED
    elif WATCHLIST in statuses or MISSING in statuses:
        verdict = WATCHLIST
    else:
        verdict = READY
    return ArcReport(dims, verdict)


def _count(directory: Path, pattern: str) -> int:
    """How many files match `pattern` in `directory` (0 if the directory is absent)."""
    return len(list(directory.glob(pattern))) if directory.is_dir() else 0


# The runtime dimensions: real capabilities, but their verdict is per-run and never stored on disk,
# so there is nothing filed for ARC to read. Honestly MISSING, not faked.
_RUNTIME = ("change", "patch", "evidence", "release")


def filed_review(root: Path | None = None) -> ArcReport:
    """Read each dimension's FILED evidence from disk and compose a verdict. Reads only."""
    base = root if root is not None else Path(__file__).resolve().parent.parent
    adrs = _count(base / "docs" / "adr", "*.md")
    tests = _count(base / "tests", "test_*.py")
    ci = (base / ".github" / "workflows" / "ci.yml").exists()
    patterns = _count(base / "docs" / "hardware_store" / "patterns", "*.md")
    benches = _count(base / "benchmarks", "*.py")
    security = _count(base / "security-evidence", "*.json")
    has_ledger = (base / "dependency_ledger.toml").exists()

    def ready(ok: bool) -> str:
        return READY if ok else MISSING

    dimensions = [
        Dimension("architecture", ready(adrs > 0), f"{adrs} ADRs on disk"),
        Dimension("testing", ready(ci and tests > 0), f"CI workflow + {tests} test files"),
        Dimension("documentation", ready(adrs > 0 and patterns > 0), f"{patterns} pattern docs"),
        Dimension("dependency", ready(has_ledger), "dependency_ledger.toml"),
        Dimension("performance", ready(benches > 0), f"{benches} benchmark files"),
        Dimension("security", ready(security > 0), f"{security} security-evidence file(s)"),
    ]
    dimensions += [_runtime_dim(name, base) for name in _RUNTIME]
    dimensions.append(_control_dim(base))
    return compose(dimensions)


def _eval_regressions(evals: list[Record]) -> list[str]:
    """Subjects whose latest ai-eval score fell below the prior one (a quality regression)."""
    by_subject: dict[str, list[Record]] = {}
    for record in evals:  # append order: the last per subject is the latest
        by_subject.setdefault(record.payload["subject"], []).append(record)
    return [
        subject
        for subject, series in by_subject.items()
        if len(series) > 1 and series[-1].payload["score"] < series[-2].payload["score"]
    ]


def _control_dim(root: Path) -> Dimension:
    """ARC's Control axis, read from the Chronicle: open serious incidents and eval regressions.

    READY when the ship's memory is clean; WATCHLIST when a high/critical incident is open or an
    ai-eval has regressed. This makes the incident and ai-eval records load-bearing on the readiness
    verdict rather than a store nothing reads. A tampered Chronicle fails loud on read (the
    Chronicle's own law), exactly as the evidence dimension does - never a false pass.
    """
    from parts import chronicle

    serious = [
        r
        for r in chronicle.incidents("open", root=root)
        if r.payload.get("severity") in ("high", "critical")
    ]
    regressions = _eval_regressions(chronicle.ai_evals(root=root))
    concerns = []
    if serious:
        concerns.append(f"{len(serious)} open high/critical incident(s)")
    if regressions:
        concerns.append(f"{len(regressions)} ai-eval regression(s): {', '.join(regressions[:3])}")
    if concerns:
        return Dimension("control", WATCHLIST, "; ".join(concerns) + " (chronicle)")
    return Dimension(
        "control", READY, "no open high/critical incident or eval regression (chronicle)"
    )


def _runtime_dim(name: str, root: Path) -> Dimension:
    """Read a runtime dimension's latest FILED verdict, or MISSING if none is filed. Reads only.

    `evidence` is read from the retained Chronicle (slice 1b); change/patch/release read their
    dated verdicts via arc_ledger. Absence is MISSING (never a pass); a malformed artifact fails
    loud (arc_ledger.VerdictError or chronicle.ChronicleError).
    """
    if name == "evidence":
        return _evidence_dim(root)
    verdict = arc_ledger.read_latest(name, root=root)
    if verdict is None:
        return Dimension(name, MISSING, "runtime capability; no filed verdict to read")
    return Dimension(name, verdict.status, f"{verdict.source} (filed {verdict.commit})")


def _evidence_dim(root: Path) -> Dimension:
    """Read the `evidence` dimension from the retained Chronicle (its `evidence` record kind).

    Slice 1b: evidence moved from the git-ignored arc-evidence/ verdict to the git-tracked,
    hash-chained Chronicle, so ARC now reads retained, cited evidence. Absence is MISSING (never a
    pass); a record with an unknown status or an empty source fails loud (ChronicleError).
    """
    from parts import chronicle

    record = chronicle.read_latest("evidence", root=root)
    if record is None:
        return Dimension("evidence", MISSING, "runtime capability; no filed verdict to read")
    status = record.payload.get("status")
    source = str(record.payload.get("source", "")).strip()
    if not isinstance(status, str) or status not in _DIM_STATUSES or not source:
        raise chronicle.ChronicleError(
            f"chronicle evidence record is malformed (status={status!r}, source={source!r})"
        )
    return Dimension("evidence", status, f"{source} (filed {record.commit}, chronicle)")


def render(report: ArcReport) -> str:
    """Project a report to the ARC Chamber panel. Text is a projection, never a mutation."""
    lines = [
        "ARC  -  Assurance, Readiness, Control",
        f"VERDICT: {report.verdict.upper()}",
        "",
    ]
    for d in report.dimensions:
        lines.append(f"  [{d.status:<9}] {d.name:<13} {d.source}")
    lines += ["", "Readiness, not certification. MISSING is never a pass."]
    return "\n".join(lines)


def arc(arg: str = "") -> str:
    """The `arc` / `arc status` verb: the ARC Chamber window onto the current readiness verdict."""
    sub = arg.strip().lower()
    if sub in ("", "status"):
        return render(filed_review())
    return "Unknown arc action. Try: arc status"
