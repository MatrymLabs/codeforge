"""CARD: integrity -- the RepoIntegrityRitual: one honest repo-health report.

Composes the checks CodeForge already owns (code quality, security, catalog
provenance, registry validity, docs presence, truth/overclaim) into one dated report
under reports/repo_integrity/. Integrity-first means honest about limits: it DETECTS
tools and points at `make check`/`make security` for the live run rather than
re-running the suite; a missing tool is reported `not_configured`, never faked; and it
never claims to prove legal originality or compliance -- only to organize evidence.

Run: `make repo-integrity` (or `python -m parts.integrity`).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404 -- fixed argv, no shell; reads `git log` for one date, read-only
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parts.hardware import load_catalog
from parts.qualitygate import gate_all
from parts.registry import load_collective, unfiled_modules, validate
from parts.shelf_boundary import shelf_boundary_gaps

_ROOT = Path(__file__).resolve().parent.parent
_REPORT_DIR = _ROOT / "reports" / "repo_integrity"

_TOOLS = (
    "ruff",
    "mypy",
    "pytest",
    "pip-audit",
    "bandit",
    "gitleaks",
    "detect-secrets",
    "cyclonedx-py",
    "semgrep",
    "scancode",
)
_PRESENCE = ("README.md", "LICENSE", "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md", "docs")
# Words that would overclaim if unqualified -- the VeritasGate red flags.
_OVERCLAIM = (
    "production-ready",
    "fully compliant",
    "cmmc compliant",
    "osha compliant",
    "certified",
    "guaranteed",
    "fully automated",
    "audit ready",
    "audit-ready",
)

# The canonical LIVING roadmaps/checklists whose forward-looking claims must be reconciled against
# the code. The overclaim scan catches "done when it isn't"; this catches the mirror -- "remaining
# when it's already built" -- so a stale claim never silently outlives the work that satisfied it.
_CLAIM_DOCS = (
    "docs/vision_resync.md",
    "docs/repository_maturity_scorecard.md",
    "docs/github_portfolio_checklist.md",
    "docs/full_stack_readiness_checklist.md",
    "docs/reports/security/security-roadmap.md",
)
# Living roadmaps that live in the SHIP repo, not this one. The ship's DEVELOPMENT_PLAN.md drives
# codeforge but sits across the repo boundary, so a claim there (a filed feature still called
# "unbuilt") is invisible to a ritual that only reads its own tree -- exactly how proactive NPCs
# stayed "a candidate future slice" in the plan after they shipped. Reaching the ship plan closes
# that cross-repo blind spot, the same way the `regs` verb reaches the FGL registry read-only.
_SHIP_CLAIM_DOCS = ("DEVELOPMENT_PLAN.md",)


def _ship_home(root: Path | None = None) -> Path | None:
    """The MatrymLabs ship checkout (where DEVELOPMENT_PLAN.md lives), or None when not mounted.
    Resolved from SHIP_HOME, else the sibling of the codeforge root. Returns None unless the plan
    is actually there, so the gate degrades cleanly off-ship (as in CI, where the ship repo isn't
    checked out) instead of failing -- a read-only seam, never a hard dependency."""
    base = root if root is not None else _ROOT
    env = os.environ.get("SHIP_HOME", "").strip()
    candidate = Path(env) if env else base.parent
    return candidate if (candidate / _SHIP_CLAIM_DOCS[0]).exists() else None


# Deliberate forward-claim markers only, to stay high-signal: an unchecked LIST-ITEM checkbox, a
# TODO, a "Remaining:/Deferred:/(" label, or a "not yet built/done/wired" phrase. A legend line
# ("`[ ]` = planned") and prose ("the remaining tests pass") are intentionally NOT matched.
_CLAIM_RE = re.compile(
    r"^\s*[-*]\s*\[ \]|\bTODO\b|\b(?:remaining|deferred)\b\s*[:(]"
    r"|\bnot yet (?:built|done|wired|implemented)\b",
    re.IGNORECASE,
)


def tool_status(which: Callable[[str], str | None] = shutil.which) -> dict[str, bool]:
    """Which integrity tools are on PATH (inside the venv). `which` is injectable."""
    return {tool: which(tool) is not None for tool in _TOOLS}


def presence_gaps(root: Path | None = None) -> list[str]:
    """Key presentation files that are missing (empty list == all present)."""
    base = root if root is not None else _ROOT
    return [name for name in _PRESENCE if not (base / name).exists()]


def overclaim_hits(root: Path | None = None) -> list[str]:
    """README phrases that would overclaim without qualified review + evidence."""
    base = root if root is not None else _ROOT
    readme = base / "README.md"
    if not readme.exists():
        return []
    text = readme.read_text(encoding="utf-8", errors="ignore").lower()
    return [phrase for phrase in _OVERCLAIM if phrase in text]


def forward_claims(root: Path | None = None, docs: tuple[str, ...] = _CLAIM_DOCS) -> list[str]:
    """Every forward-looking claim in the canonical living roadmaps, as `doc:line: text`.

    A reconciliation queue, not a verdict: this ritual cannot know whether a claim is still true,
    only that it exists. Surfacing the queue is the point -- reverse drift (a "remaining" that the
    code already satisfied) rots silently until someone stumbles on it; listed, it gets reviewed.
    Confirm each is still pending, or tick it done and cite the evidence."""
    base = root if root is not None else _ROOT
    hits: list[str] = []

    def scan(path: Path, label: str) -> None:
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if _CLAIM_RE.search(line):
                hits.append(f"{label}:{lineno}: {line.strip()[:90]}")

    for rel in docs:  # this repo's roadmaps
        scan(base / rel, rel)
    ship = _ship_home(base)  # the ship's plan, across the repo boundary (when mounted)
    if ship is not None:
        for rel in _SHIP_CLAIM_DOCS:
            scan(ship / rel, f"ship:{rel}")
    return hits


# Evidence currency: the mirror of the forward-claim queue, aimed one layer up. forward_claims
# catches a roadmap that says "remaining" for shipped work; this catches shipped CAPABILITY that
# never reached the evidence surfaces (the Career Evidence board, and by extension the storefront).
# A convergence review found exactly this: six PRs of supply-chain tooling shipped while the board
# claimed none of it. The signal is git-grounded (capability changed AFTER the board's last update),
# so it fires the moment a build arc outruns its evidence, not on a calendar the board could dodge.
_CAREER_MATRIX = "data/career/career_evidence_matrix.json"
_CAPABILITY_PATHS = ("parts", ".github/workflows", "forge.py")
_CURRENCY_STALE_DAYS = 30  # calendar fallback when git history is unavailable (e.g. a tarball)


def _latest_capability_change(root: Path | None = None) -> date | None:
    """The date of the newest commit touching a capability path (`parts/`, workflows, `forge.py`),
    read from git. None when git or the history is unavailable (a tarball, a shallow clone with the
    path unchanged): a read-only seam, so the currency check degrades to a calendar fallback instead
    of failing. Injected into `career_currency_gaps` so the pure check never shells git in tests."""
    base = root if root is not None else _ROOT
    try:
        proc = subprocess.run(  # nosec B603 B607 -- fixed argv, no shell; git log, read-only
            [
                "git",
                "-C",
                str(base),
                "log",
                "-1",
                "--format=%cd",
                "--date=short",
                "--",
                *_CAPABILITY_PATHS,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stamp = proc.stdout.strip()
    if proc.returncode != 0 or not stamp:
        return None
    try:
        return date.fromisoformat(stamp)
    except ValueError:
        return None


def career_currency_gaps(
    root: Path | None = None,
    today: date | None = None,
    capability_change: date | None = None,
) -> list[str]:
    """Reconciliation queue for evidence currency: has shipped capability outrun the career board?

    A queue, not a verdict (like `forward_claims`): it cannot know whether the newest capability is
    board-worthy, only that the board has not been touched since it shipped. Prefer the git-grounded
    signal (`capability_change` after the board's `last_updated`); with no git, fall back to a plain
    calendar staleness so the check still nudges off-VCS. The fix is always human: claim the shipped
    work on the board (and storefront), or bump `last_updated` once you confirm it is current."""
    base = root if root is not None else _ROOT
    stamp = today if today is not None else date.today()
    path = base / _CAREER_MATRIX
    if not path.exists():
        return []
    try:
        board = json.loads(path.read_text(encoding="utf-8"))["career_board"]
        last = date.fromisoformat(board["last_updated"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return [f"{_CAREER_MATRIX}: last_updated is missing or unparseable"]
    if capability_change is not None:
        if capability_change > last:
            return [
                f"capability changed {capability_change.isoformat()} after the career board's last "
                f"update {last.isoformat()}: claim the shipped work on the board (and storefront), "
                "or bump last_updated once confirmed current."
            ]
        return []  # board is current with respect to the newest capability change
    if (stamp - last).days > _CURRENCY_STALE_DAYS:
        return [
            f"career board last updated {last.isoformat()} ({(stamp - last).days} days ago; no git "
            "to check capability): run a convergence pass to confirm shipped work is claimed."
        ]
    return []


@dataclass(frozen=True)
class _ReportData:
    """The signals the report is assembled from -- gathered once, then rendered. Splitting the
    gather from the render keeps build_report a thin orchestrator, not a 30-branch monolith."""

    parts_count: int
    status_summary: str
    no_influence: list[str]
    reg_problems: list[str]
    gaps: list[str]
    overclaims: list[str]
    claims: list[str]
    n_roadmaps: int
    currency: list[str]
    boundary: list[str]
    qa: Counter[str]


def _gather_signals(base: Path, stamp: date, tools: dict[str, bool]) -> _ReportData:
    """Run every in-process check the report reads: catalog, registry (+ completeness), presence,
    overclaim, forward-claim + evidence-currency queues, and QA readiness. No I/O of its own beyond
    the checks it composes."""
    parts = load_catalog()
    by_status: dict[str, int] = {}
    for p in parts:
        by_status[p.source_status] = by_status.get(p.source_status, 0) + 1

    records = load_collective()
    reg_problems = validate(records) if records else ["registry empty"]
    # Completeness: the registry claims to file the code modules themselves, so an unfiled
    # module is a real gap the internal-consistency validate() cannot see.
    reg_problems += [f"unfiled module: {m}" for m in unfiled_modules(records)]

    return _ReportData(
        parts_count=len(parts),
        status_summary=", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) or "none",
        no_influence=[p.id for p in parts if not p.influence],
        reg_problems=reg_problems,
        gaps=presence_gaps(base),
        overclaims=overclaim_hits(base),
        claims=forward_claims(base),
        n_roadmaps=len(_CLAIM_DOCS) + (len(_SHIP_CLAIM_DOCS) if _ship_home(base) else 0),
        currency=career_currency_gaps(base, stamp, _latest_capability_change(base)),
        boundary=shelf_boundary_gaps(base),
        qa=Counter(r.verdict for r in gate_all(records)),  # keys: pass | watch | fail
    )


def _next_actions(tools: dict[str, bool], data: _ReportData) -> list[str]:
    """The recommended next actions: one per open gap, in fixed order; a clean-bill line if none."""
    actions: list[str] = []
    if not (tools.get("gitleaks") or tools.get("detect-secrets")):
        actions.append("Configure secret scanning: add `make secrets` (detect-secrets, baselined).")
    if data.gaps:
        actions.append(f"Add missing presentation files: {', '.join(data.gaps)}.")
    if data.reg_problems:
        actions.append(f"Fix registry: {'; '.join(data.reg_problems)}.")
    if data.overclaims:
        actions.append(f"Soften overclaims in README: {', '.join(data.overclaims)}.")
    if data.claims:
        n_claims = len(data.claims)
        actions.append(
            f"Reconcile {n_claims} forward claim(s) in the living roadmaps against the code "
            "(reverse-drift): confirm each is still pending, or tick it done and cite the evidence."
        )
    if data.currency:
        actions.append(
            "Reconcile evidence currency: claim shipped capability on the board + storefront,"
            " or bump last_updated once confirmed current."
        )
    if data.boundary:
        actions.append(
            "Restore the shelf boundary: a Hardware Store core imports an engine part, "
            f"re-coupling it ({'; '.join(data.boundary)}). Move the dependency or the core."
        )
    if not actions:
        actions.append(
            "No blocking gaps found - run `make check` + `make security` for the live gates."
        )
    return actions


def _report_lines(
    base: Path, stamp: date, tools: dict[str, bool], data: _ReportData, actions: list[str]
) -> list[str]:
    """Render the gathered signals into the report's exact lines (presentation only, no checks)."""

    def tool_line(name: str, live: str) -> str:
        return f"detected (run `{live}`)" if tools.get(name) else "not_configured"

    reg_line = "yes" if not data.reg_problems else "NO -- " + "; ".join(data.reg_problems)
    overclaim_line = "none found" if not data.overclaims else "FLAGS: " + ", ".join(data.overclaims)
    secret_scan = (
        "detected"
        if (tools.get("gitleaks") or tools.get("detect-secrets"))
        else "not_configured - recommend detect-secrets (baselined) or gitleaks"
    )
    qa_line = f"{data.qa['pass']} pass, {data.qa['watch']} watch, {data.qa['fail']} fail"
    boundary_line = (
        "clean (engine -> shelf, one way)"
        if not data.boundary
        else "VIOLATED -- " + "; ".join(data.boundary)
    )
    n_claims = len(data.claims)
    lines = [
        "CodeForge Repo Integrity Report",
        "",
        f"Timestamp:     {stamp.isoformat()}",
        f"Project Root:  {base.name}",
        "",
        "Code Quality:",
        f"- ruff:         {tool_line('ruff', 'make lint')}",
        f"- mypy:         {tool_line('mypy', 'make typecheck')}",
        f"- pytest:       {tool_line('pytest', 'make test')}",
        "  (full run via `make check` -- this report detects tools, it does not re-run the suite)",
        "",
        "Security:",
        f"- bandit (SAST):     {tool_line('bandit', 'make security')}",
        f"- pip-audit (deps):  {tool_line('pip-audit', 'make security')}",
        f"- secret scan:       {secret_scan}",
        "",
        "License / Source Origin:",
        f"- project LICENSE:   {'present' if (base / 'LICENSE').exists() else 'MISSING'}",
        f"- catalog parts:     {data.parts_count}  ({data.status_summary})",
        f"- parts missing pattern (influence): {', '.join(data.no_influence) or 'none'}",
        "- dependency licenses: not scanned (scancode not_configured -- see limitations)",
        "",
        "Originality Awareness:",
        f"- by source_status:  {data.status_summary}",
        "- similarity scan:   not run (no code uploaded to any third-party service)",
        "- LIMITATION:        this organizes evidence; it does NOT prove universal originality.",
        "",
        "Professional Presentation:",
        f"- key files:  {'all present' if not data.gaps else 'MISSING: ' + ', '.join(data.gaps)}",
        "",
        "Truth / VeritasGate:",
        f"- registry validates:   {reg_line}",
        f"- QA readiness:         {qa_line}",
        f"- overclaim scan:       {overclaim_line}",
        f"- forward-claim queue:  {n_claims} to reconcile across {data.n_roadmaps} roadmaps "
        f"(reverse-drift{' incl. ship plan' if _ship_home(base) else ''}; a queue, not a verdict)",
        f"- evidence currency:    {len(data.currency)} career-board reconciliation(s) "
        "(shipped capability vs the claimed board; a queue, not a verdict)",
        "",
        "Architecture / Hardware Store:",
        f"- shelf boundary:       {boundary_line}",
    ]
    lines += [f"    {c}" for c in data.claims]  # the full queue: curated docs keep it bounded
    lines += [f"    {c}" for c in data.currency]
    lines += [
        "",
        "Recommended Next Actions:",
    ]
    lines += [f"{i}. {a}" for i, a in enumerate(actions, start=1)]
    lines += [
        "",
        "This report organizes evidence. It does not prove legal originality, security,",
        "or compliance. Similarity is a signal; license metadata is evidence; tests prove",
        "behavior; documentation proves intent; human judgment makes the call.",
    ]
    return lines


def build_report(
    root: Path | None = None, today: date | None = None, tools: dict[str, bool] | None = None
) -> str:
    """Assemble the integrity report from in-process signals + tool detection.

    A thin orchestrator: gather the signals once, decide the next actions, render the lines. `tools`
    is injectable (a name->present map) so tests are deterministic whatever is installed."""
    base = root if root is not None else _ROOT
    stamp = today if today is not None else date.today()
    tools = tools if tools is not None else tool_status()
    data = _gather_signals(base, stamp, tools)
    actions = _next_actions(tools, data)
    return "\n".join(_report_lines(base, stamp, tools, data, actions))


def save_report(text: str, root: Path | None = None, today: date | None = None) -> Path:
    """Write the report under reports/repo_integrity/<date>-repo-integrity.md via the shared
    ReportWriter (one dated-report seam for every producer)."""
    from parts.shelf.reporting import write_report

    stamp = (today if today is not None else date.today()).isoformat()
    return write_report("repo_integrity", text, root=root, stamp=stamp, slug="repo-integrity")


def run_repo_integrity() -> Path:
    """Build the report, save it, and return its path (the `make repo-integrity` entry)."""
    text = build_report()
    path = save_report(text)
    print(text)
    print(f"\nSaved: {path.relative_to(_ROOT)}")
    return path


if __name__ == "__main__":
    run_repo_integrity()
