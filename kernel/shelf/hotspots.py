"""CARD: hotspots -- rank technical-debt hotspots by change-frequency x complexity.

The second rung of the R&D Governance Lab (from the "Repo Structure, Auditing, QC & PM"
brief, which calls churn x complexity hotspot ranking "a high-value, differentiated
feature" - CodeScene's behavioural-analysis method, reproducible from git log data
without a commercial license). The insight: complicated code that changes often carries
"a high interest rate" - it is where debt actually hurts. Typically only 2-4% of a
codebase, and that is exactly where to focus.

A hotspot scores high only when a file is BOTH frequently changed AND complex: the score
is the product of normalized churn and normalized complexity, so a stable-but-complex file
and a churny-but-simple file both rank low, and the churny-AND-complex file floats to the
top-right of CodeScene's scatter.

Both inputs are INJECTED (a seam): `rank` takes a churn map and a complexity map, so tests
never run git or a profiler. `churn_from_log` parses `git log` output and
`complexity_from_sources` computes McCabe complexity from source - for real use.

Clean-room, stdlib only (`ast`).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

CAVEAT = (
    "A hotspot is a PRIORITIZATION hint, not a defect list. Churn reflects THIS history "
    "window (new files with little history under-rank); complexity is a proxy for debt, "
    "not a proof of it. Read the top hotspots first; do not treat rank as a bug."
)

_DECISION = (
    ast.If,
    ast.IfExp,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
)


class HotspotError(ValueError):
    """Raised on malformed input."""


@dataclass(frozen=True)
class Hotspot:
    """One file with its change-frequency, complexity, and combined hotspot score."""

    path: str
    churn: int  # number of commits that touched it
    complexity: int  # McCabe cyclomatic complexity (whole file)
    score: float  # normalized_churn * normalized_complexity, in [0, 1]


@dataclass(frozen=True)
class HotspotReport:
    """The ranked hotspot report - a prioritization hint, honestly bounded."""

    hotspots: tuple[Hotspot, ...] = ()  # descending score
    file_count: int = 0
    caveat: str = CAVEAT
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def prime_hotspot(self) -> str:
        return self.hotspots[0].path if self.hotspots and self.hotspots[0].score > 0 else ""


def rank(
    churn: dict[str, int],
    complexity: dict[str, int],
    *,
    top: int = 20,
) -> HotspotReport:
    """Rank files by normalized churn x normalized complexity.

    churn:      {path: number of commits that touched it}
    complexity: {path: McCabe complexity of the file}
    Only files present in BOTH maps are ranked (a file needs both a history and code).
    """
    if not isinstance(churn, dict) or not isinstance(complexity, dict):
        raise HotspotError("churn and complexity must both be dicts of {path: number}")

    shared = sorted(set(churn) & set(complexity))
    notes: list[str] = []
    only_churn = set(churn) - set(complexity)
    only_cx = set(complexity) - set(churn)
    if only_churn:
        notes.append(f"{len(only_churn)} changed file(s) had no measured complexity (skipped)")
    if only_cx:
        notes.append(f"{len(only_cx)} code file(s) had no change history (skipped)")

    if not shared:
        return HotspotReport(hotspots=(), file_count=0, notes=tuple(notes))

    max_churn = max(churn[p] for p in shared) or 1
    max_cx = max(complexity[p] for p in shared) or 1

    hotspots = [
        Hotspot(
            path=p,
            churn=churn[p],
            complexity=complexity[p],
            score=round((churn[p] / max_churn) * (complexity[p] / max_cx), 6),
        )
        for p in shared
    ]
    hotspots.sort(key=lambda h: (-h.score, h.path))
    return HotspotReport(
        hotspots=tuple(hotspots[:top]),
        file_count=len(shared),
        notes=tuple(notes),
    )


def churn_from_log(git_log_output: str) -> dict[str, int]:
    """Count commits per file from `git log --format=%H --name-only` output.

    Each commit is a hash line followed by the files it touched; a file's churn is the
    number of distinct commits that listed it.
    """
    churn: dict[str, int] = {}
    seen_this_commit: set[str] = set()
    for raw in git_log_output.splitlines():
        line = raw.strip()
        if not line:
            continue
        # a 40-char (or 64-char sha256) hex string is a commit boundary, not a filename
        if len(line) in (40, 64) and all(c in "0123456789abcdef" for c in line):
            seen_this_commit = set()
            continue
        if line not in seen_this_commit:
            seen_this_commit.add(line)
            churn[line] = churn.get(line, 0) + 1
    return churn


def _file_complexity(tree: ast.Module) -> int:
    """McCabe cyclomatic complexity of a whole module: 1 + decision points."""
    score = 1
    for node in ast.walk(tree):
        if isinstance(node, _DECISION):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += 1 + len(node.ifs)
    return score


def complexity_from_sources(sources: dict[str, str]) -> dict[str, int]:
    """Compute McCabe complexity per file from {path: source}. Unparseable files are skipped."""
    out: dict[str, int] = {}
    for path, source in sources.items():
        try:
            out[path] = _file_complexity(ast.parse(source))
        except SyntaxError:
            continue
    return out


def render(report: HotspotReport, *, top: int = 10) -> str:
    """A human-readable rendering of the ranked hotspots."""
    lines = [f"hotspots (churn x complexity): {report.file_count} files ranked"]
    for note in report.notes:
        lines.append(f"  note: {note}")
    shown = [h for h in report.hotspots if h.score > 0][:top]
    if shown:
        lines.append("  top hotspots (refactor-first candidates):")
        for h in shown:
            lines.append(f"    {h.score:.4f}  churn {h.churn:<4} cx {h.complexity:<4}  {h.path}")
    else:
        lines.append("  no hotspots (no file is both changed and complex)")
    lines.append("  CAVEAT: " + report.caveat)
    return "\n".join(lines)
