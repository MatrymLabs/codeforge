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

import shutil
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path

from parts.hardware import load_catalog
from parts.qualitygate import gate_all
from parts.registry import load_collective, validate

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


def build_report(
    root: Path | None = None, today: date | None = None, tools: dict[str, bool] | None = None
) -> str:
    """Assemble the integrity report from in-process signals + tool detection.

    `tools` is injectable (a name->present map) so tests are deterministic regardless
    of what's installed in the current environment."""
    base = root if root is not None else _ROOT
    stamp = today if today is not None else date.today()
    tools = tools if tools is not None else tool_status()

    def tool_line(name: str, live: str) -> str:
        return f"detected (run `{live}`)" if tools.get(name) else "not_configured"

    parts = load_catalog()
    by_status: dict[str, int] = {}
    for p in parts:
        by_status[p.source_status] = by_status.get(p.source_status, 0) + 1
    no_influence = [p.id for p in parts if not p.influence]

    records = load_collective()
    reg_problems = validate(records) if records else ["registry empty"]
    gaps = presence_gaps(base)
    overclaims = overclaim_hits(base)
    qa = Counter(r.verdict for r in gate_all(records))  # keys: pass | watch | fail

    status_summary = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) or "none"
    reg_line = "yes" if not reg_problems else "NO -- " + "; ".join(reg_problems)
    overclaim_line = "none found" if not overclaims else "FLAGS: " + ", ".join(overclaims)
    secret_scan = (
        "detected"
        if (tools.get("gitleaks") or tools.get("detect-secrets"))
        else "not_configured - recommend detect-secrets (baselined) or gitleaks"
    )
    next_actions = []
    if not (tools.get("gitleaks") or tools.get("detect-secrets")):
        next_actions.append(
            "Configure secret scanning: add `make secrets` (detect-secrets, baselined)."
        )
    if gaps:
        next_actions.append(f"Add missing presentation files: {', '.join(gaps)}.")
    if reg_problems:
        next_actions.append(f"Fix registry: {'; '.join(reg_problems)}.")
    if overclaims:
        next_actions.append(f"Soften overclaims in README: {', '.join(overclaims)}.")
    if not next_actions:
        next_actions.append(
            "No blocking gaps found - run `make check` + `make security` for the live gates."
        )

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
        f"- catalog parts:     {len(parts)}  ({status_summary})",
        f"- parts missing pattern (influence): {', '.join(no_influence) or 'none'}",
        "- dependency licenses: not scanned (scancode not_configured -- see limitations)",
        "",
        "Originality Awareness:",
        f"- by source_status:  {status_summary}",
        "- similarity scan:   not run (no code uploaded to any third-party service)",
        "- LIMITATION:        this organizes evidence; it does NOT prove universal originality.",
        "",
        "Professional Presentation:",
        f"- key files:  {'all present' if not gaps else 'MISSING: ' + ', '.join(gaps)}",
        "",
        "Truth / VeritasGate:",
        f"- registry validates:   {reg_line}",
        f"- QA readiness:         {qa['pass']} pass, {qa['watch']} watch, {qa['fail']} fail",
        f"- overclaim scan:       {overclaim_line}",
        "",
        "Recommended Next Actions:",
    ]
    lines += [f"{i}. {a}" for i, a in enumerate(next_actions, start=1)]
    lines += [
        "",
        "This report organizes evidence. It does not prove legal originality, security,",
        "or compliance. Similarity is a signal; license metadata is evidence; tests prove",
        "behavior; documentation proves intent; human judgment makes the call.",
    ]
    return "\n".join(lines)


def save_report(text: str, root: Path | None = None, today: date | None = None) -> Path:
    """Write the report under reports/repo_integrity/<date>.md (created if absent)."""
    base_dir = (root / "reports" / "repo_integrity") if root is not None else _REPORT_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    stamp = today if today is not None else date.today()
    path = base_dir / f"{stamp.isoformat()}-repo-integrity.md"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def run_repo_integrity() -> Path:
    """Build the report, save it, and return its path (the `make repo-integrity` entry)."""
    text = build_report()
    path = save_report(text)
    print(text)
    print(f"\nSaved: {path.relative_to(_ROOT)}")
    return path


if __name__ == "__main__":
    run_repo_integrity()
