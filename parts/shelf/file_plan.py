"""CARD: file_plan -- lint a repository against its file-plan and score structural compliance.

The first rung of the R&D Governance Lab (from the "Repo Structure, Auditing, QC & PM"
brief). The brief is explicit: repolinter is archived, so CodeForge should implement its
own structure linter - checking that a repo carries the canonical files (README, LICENSE,
pyproject), follows src-layout, and keeps config out of code. This encodes a "file plan"
as a versioned, composable set of rules (the brief's FilePlanRule record) and reports
which a repo satisfies plus a weighted compliance score.

Each rule is data (id, what to detect, severity, weight), so a plan is a library a repo is
graded against - detection now, scaffolding later, scoring throughout (the parts-factory
ingest -> normalize -> re-emit pattern).

The listing is INJECTED (a seam): `check` takes the set of repo-relative paths, so tests
never touch a real filesystem. `scan` walks a directory into that set for real use.

Clean-room, stdlib only (`fnmatch`, `pathlib`).
"""

from __future__ import annotations

import fnmatch
import pathlib
from collections.abc import Iterable
from dataclasses import dataclass, field

# rule kinds: how a rule is checked against the repo's path listing
_KINDS = ("present", "absent", "glob", "any_of")


class FilePlanError(ValueError):
    """Raised on a malformed rule or plan."""


@dataclass(frozen=True)
class FilePlanRule:
    """One structural convention: what to look for, how much it matters."""

    id: str
    description: str
    kind: str  # "present" | "absent" | "glob" | "any_of"
    targets: tuple[str, ...]  # path(s) or glob(s) to check
    severity: str = "warn"  # "error" | "warn" | "info"
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise FilePlanError(f"unknown rule kind {self.kind!r} for {self.id}; choose {_KINDS}")
        if self.severity not in ("error", "warn", "info"):
            raise FilePlanError(f"unknown severity {self.severity!r} for {self.id}")
        if not self.targets:
            raise FilePlanError(f"rule {self.id} has no targets")


@dataclass(frozen=True)
class Finding:
    """The result of checking one rule against a repo."""

    rule_id: str
    ok: bool
    severity: str
    description: str
    detail: str


@dataclass(frozen=True)
class PlanReport:
    """The validated file-plan compliance report."""

    findings: tuple[Finding, ...] = ()
    score: float = 1.0  # weighted share of satisfied rules (0..1)
    passed: bool = True  # no failing rule of severity "error"
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def failures(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if not f.ok)

    @property
    def blocking_failures(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if not f.ok and f.severity == "error")


# The canonical Python-repo file plan (the brief's src-layout tree). A caller can pass its own.
DEFAULT_PLAN: tuple[FilePlanRule, ...] = (
    FilePlanRule(
        "fp.readme",
        "a README is present",
        "any_of",
        ("README.md", "README.rst", "README.txt"),
        "error",
        1.5,
    ),
    FilePlanRule(
        "fp.license",
        "a LICENSE is present",
        "any_of",
        ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"),
        "error",
        1.5,
    ),
    FilePlanRule(
        "fp.pyproject",
        "pyproject.toml is the single source of truth",
        "present",
        ("pyproject.toml",),
        "error",
        1.5,
    ),
    FilePlanRule("fp.gitignore", ".gitignore is present", "present", (".gitignore",), "warn", 1.0),
    FilePlanRule(
        "fp.tests",
        "a tests directory exists",
        "glob",
        ("tests/*", "test/*", "*/tests/*"),
        "warn",
        1.0,
    ),
    FilePlanRule(
        "fp.ci",
        "a CI workflow is present",
        "glob",
        (".github/workflows/*.yml", ".github/workflows/*.yaml"),
        "warn",
        1.0,
    ),
    FilePlanRule(
        "fp.changelog",
        "a CHANGELOG is present",
        "any_of",
        ("CHANGELOG.md", "CHANGELOG.rst", "CHANGES.md"),
        "info",
        0.5,
    ),
    FilePlanRule(
        "fp.no-setup-py",
        "no legacy setup.py (declarative packaging)",
        "absent",
        ("setup.py",),
        "info",
        0.5,
    ),
    FilePlanRule(
        "fp.no-committed-env",
        "no committed .env (secrets stay out of git)",
        "absent",
        (".env",),
        "error",
        1.0,
    ),
)


def _matches(target: str, paths: set[str]) -> bool:
    """A path equals the target, or (for a glob target) any path matches it."""
    if target in paths:
        return True
    if any(ch in target for ch in "*?["):
        return any(fnmatch.fnmatch(p, target) for p in paths)
    return False


def _check_rule(rule: FilePlanRule, paths: set[str]) -> bool:
    if rule.kind == "present":
        return _matches(rule.targets[0], paths)
    if rule.kind == "absent":
        return not any(_matches(t, paths) for t in rule.targets)
    if rule.kind in ("glob", "any_of"):
        return any(_matches(t, paths) for t in rule.targets)
    raise FilePlanError(
        f"unhandled kind {rule.kind!r}"
    )  # pragma: no cover - guarded in __post_init__


def check(paths: Iterable[str], plan: tuple[FilePlanRule, ...] = DEFAULT_PLAN) -> PlanReport:
    """Grade a repo (given its set of relative paths) against a file plan.

    paths: repo-relative file paths (e.g. from `scan` or a git listing).
    Returns a PlanReport with per-rule findings, a weighted compliance score, and whether
    every "error"-severity rule is satisfied (passed).
    """
    if not plan:
        raise FilePlanError("an empty plan grades nothing")

    def _norm(p: str) -> str:
        p = p.replace("\\", "/")
        return p.removeprefix("./")

    path_set = {_norm(p) for p in paths}

    findings: list[Finding] = []
    earned = 0.0
    total = 0.0
    for rule in plan:
        ok = _check_rule(rule, path_set)
        total += rule.weight
        if ok:
            earned += rule.weight
        detail = "satisfied" if ok else f"expected {rule.kind}: {', '.join(rule.targets)}"
        findings.append(Finding(rule.id, ok, rule.severity, rule.description, detail))

    score = round(earned / total, 4) if total else 1.0
    blocking = [f for f in findings if not f.ok and f.severity == "error"]
    notes: list[str] = []
    if blocking:
        notes.append(f"{len(blocking)} blocking (error-severity) rule(s) unmet")
    return PlanReport(
        findings=tuple(findings),
        score=score,
        passed=not blocking,
        notes=tuple(notes),
    )


def scan(
    root: pathlib.Path,
    *,
    ignore_dirs: tuple[str, ...] = (".git", ".venv", "__pycache__", "node_modules"),
) -> set[str]:
    """Walk a directory into a set of repo-relative file paths (for real use)."""
    root = pathlib.Path(root)
    paths: set[str] = set()
    for p in root.rglob("*"):
        if p.is_file() and not any(part in ignore_dirs for part in p.parts):
            paths.add(p.relative_to(root).as_posix())
    return paths


def render(report: PlanReport) -> str:
    """A human-readable rendering of the file-plan report."""
    verdict = "PASS" if report.passed else "FAIL"
    lines = [f"file plan: [{verdict}]  compliance score {report.score}"]
    for f in report.findings:
        mark = "ok " if f.ok else "MISS"
        lines.append(f"  [{mark}] ({f.severity}) {f.rule_id}: {f.description}")
        if not f.ok:
            lines[-1] += f"  -> {f.detail}"
    for note in report.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
