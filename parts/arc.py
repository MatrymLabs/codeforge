"""CARD: arc -- ARC (Assurance, Readiness, Control): compose gate verdicts into one honest report.

CodeForge's umbrella engineering-review system, the coherent Blueprint filed as `arc`. ARC adds
NO new gate: it READS the verdicts of the ten review dimensions CodeForge already has and composes
them into one honest overall verdict (ready | watchlist | blocked). Two load-bearing rules keep it
truthful: a dimension whose gate has not been wired or has never run is MISSING, and MISSING is
never a pass; and every dimension cites the source its status came from, never an invented one.

This is slice 1 (docs `blueprints/arc.md`): the pure `compose()` core and the `arc` verb (the ARC
Chamber panel). The ten dimensions are declared here and reported MISSING until slice 2 wires each
to its real gate output. ARC is a reader: it mutates no state and runs no gate as a side effect
(architecture law 1). The world is the interface; `arc` is the room's window.
"""

from __future__ import annotations

from dataclasses import dataclass

# Per-dimension status. MISSING = no wired source yet, or a gate that never ran: never a pass.
READY = "ready"
WATCHLIST = "watchlist"
BLOCKED = "blocked"
MISSING = "missing"
_DIM_STATUSES = (READY, WATCHLIST, BLOCKED, MISSING)

# The ten review dimensions ARC composes, each with the existing gate it will read in slice 2.
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


def _unwired_review() -> ArcReport:
    """Slice 1: every dimension declared and reported MISSING, naming the gate slice 2 will wire."""
    return compose(
        [
            Dimension(name, MISSING, f"{source} (not wired yet: slice 2)")
            for name, source in DIMENSIONS
        ]
    )


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
        return render(_unwired_review())
    return "Unknown arc action. Try: arc status"
