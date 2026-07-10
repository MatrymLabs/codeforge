"""CARD: career -- the Career Evidence Sign: map CodeForge work to job-ready skills.

A data-driven proof board. It reads data/career/career_evidence_matrix.json (grounded in
BLS/O*NET research) and renders, per level, each skill with the exact repo artifact that
proves it -- and the honest gaps. It never says "job-ready"; it says "here is the skill,
here is the proof, here is what is missing."

VeritasGate rule, enforced here: a skill marked `proven` or `partial` must cite at least
one repo path that actually exists. `unproven_claims()` finds violations; the test twin
pins that the shipped board has none, so the sign cannot quietly overclaim.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MATRIX = _ROOT / "data" / "career" / "career_evidence_matrix.json"

PROVEN = "proven"
PARTIAL = "partial"
MISSING = "missing"
PLANNED = "planned"
NEEDS_UPDATE = "needs_update"
HUMAN_REVIEW = "human_review_required"

_GLYPH = {
    PROVEN: "[x]",
    PARTIAL: "[~]",
    MISSING: "[ ]",
    PLANNED: "[.]",
    NEEDS_UPDATE: "[!]",
    HUMAN_REVIEW: "[?]",
}
# Statuses that CLAIM evidence -- they must cite a real artifact (VeritasGate).
_CLAIMS_EVIDENCE = (PROVEN, PARTIAL)
_LEVELS = ("entry", "intermediate", "advanced")


class CareerError(Exception):
    """A malformed or missing evidence matrix -- fail loud, never render a lie."""


def load_board(path: Path | None = None) -> dict:
    """Load and validate the evidence matrix; a malformed file fails loud (a GATE)."""
    src = path or _MATRIX
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CareerError(f"unreadable career matrix at {src}: {exc}") from exc
    board = data.get("career_board")
    if not isinstance(board, dict) or "levels" not in board:
        raise CareerError("career matrix missing 'career_board' / 'levels'")
    for lvl in board["levels"]:
        for skill in lvl.get("skills", []):
            for req in ("skill_id", "skill", "status", "repo_proof", "next_proof_task"):
                if req not in skill:
                    raise CareerError(f"skill {skill.get('skill_id', '?')} missing '{req}'")
    return board


def _skills(board: dict) -> list[dict]:
    return [s for lvl in board["levels"] for s in lvl.get("skills", [])]


def unproven_claims(board: dict, root: Path | None = None) -> list[str]:
    """VeritasGate: proven/partial skills whose cited proof paths do NOT exist on disk.
    An empty list means every claim of evidence points to a real artifact."""
    base = root or _ROOT
    bad: list[str] = []
    for s in _skills(board):
        if s["status"] in _CLAIMS_EVIDENCE and not any(
            (base / p).exists() for p in s["repo_proof"]
        ):
            bad.append(f"{s['skill_id']} ({s['status']}) -- no cited proof path exists")
    return bad


def _counts(skills: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in skills:
        out[s["status"]] = out.get(s["status"], 0) + 1
    return out


def _render_skill(s: dict) -> list[str]:
    proof = ", ".join(s["repo_proof"]) or "(none yet)"
    return [
        f"  {_GLYPH.get(s['status'], '[ ]')} {s['skill']}",
        f"      why:   {s.get('why_it_matters', '')}",
        f"      proof: {proof}",
        f"      status: {s['status']}   next: {s['next_proof_task']}",
    ]


def _render_level(board: dict, level: str) -> list[str]:
    lvl = next((x for x in board["levels"] if x["level"] == level), None)
    if lvl is None:
        return [f"  (no such level: {level})"]
    lines = [
        f"{level.upper()}-LEVEL READINESS",
        f"  target roles: {', '.join(lvl.get('target_roles', []))}",
        "",
    ]
    for s in lvl.get("skills", []):
        lines += _render_skill(s)
        lines.append("")
    return lines


def _header(board: dict) -> list[str]:
    return [
        "CAREER EVIDENCE SIGN - CodeForge Skills-to-Proof Board",
        "",
        board.get("purpose", ""),
        f"  {board.get('market_note', '')}",
        f"  legend: {board.get('status_legend', '')}",
        "",
    ]


def render_overview(board: dict | None = None) -> str:
    b = board or load_board()
    skills = _skills(b)
    c = _counts(skills)
    lines = _header(b)
    lines.append("READINESS AT A GLANCE")
    for level in _LEVELS:
        lc = _counts([s for lvl in b["levels"] if lvl["level"] == level for s in lvl["skills"]])
        lines.append(
            f"  {level:<12} proven {lc.get(PROVEN, 0)} · partial {lc.get(PARTIAL, 0)} "
            f"· missing {lc.get(MISSING, 0)}"
        )
    lines += [
        "",
        f"  TOTAL  proven {c.get(PROVEN, 0)} · partial {c.get(PARTIAL, 0)} · "
        f"missing {c.get(MISSING, 0)} of {len(skills)} skills",
        "",
        "  views:  career checklist · career gaps · career evidence · career resume",
        "          career role entry|intermediate|advanced",
    ]
    return "\n".join(lines)


def render_checklist(board: dict | None = None) -> str:
    b = board or load_board()
    lines = _header(b)
    for level in _LEVELS:
        lines += _render_level(b, level)
    return "\n".join(lines).rstrip()


def render_role(level: str, board: dict | None = None) -> str:
    b = board or load_board()
    if level not in _LEVELS:
        return f"Unknown level '{level}'. Try: entry · intermediate · advanced"
    return "\n".join(_header(b) + _render_level(b, level)).rstrip()


def render_gaps(board: dict | None = None) -> str:
    b = board or load_board()
    gaps = [s for s in _skills(b) if s["status"] in (PARTIAL, MISSING, PLANNED, NEEDS_UPDATE)]
    lines = ["CAREER EVIDENCE SIGN - GAPS (what to build next)", ""]
    if not gaps:
        lines.append("  No gaps recorded - every tracked skill has current proof.")
        return "\n".join(lines)
    for s in sorted(gaps, key=lambda x: x["status"]):
        lines.append(f"  {_GLYPH.get(s['status'], '[ ]')} {s['skill']}  ({s['status']})")
        lines.append(f"      next: {s['next_proof_task']}")
    lines += [
        "",
        f"  {len(gaps)} gap(s). Close a gap by shipping the artifact, then flip its status.",
    ]
    return "\n".join(lines)


def render_evidence(board: dict | None = None) -> str:
    b = board or load_board()
    lines = ["CAREER EVIDENCE SIGN - PROOF PATHS", ""]
    for s in _skills(b):
        if s["status"] in _CLAIMS_EVIDENCE:
            lines.append(f"  {_GLYPH.get(s['status'])} {s['skill']}")
            lines.append(f"      {', '.join(s['repo_proof'])}")
    return "\n".join(lines)


def render_resume(board: dict | None = None) -> str:
    """Resume translation, generated from the board so it can never drift from the proof."""
    b = board or load_board()
    proven = [s["skill"] for s in _skills(b) if s["status"] == PROVEN]
    roles = sorted({r for lvl in b["levels"] for r in lvl.get("target_roles", [])})
    lines = [
        "CAREER EVIDENCE SIGN - RESUME TRANSLATION",
        "",
        "CodeForge demonstrates the ability to design and run Python software systems with",
        "automation, documentation, testing, AI-assisted development, reusable tooling, and",
        "evidence-based engineering discipline.",
        "",
        "Proven in-repo (each backed by a cited artifact):",
    ]
    lines += [f"  - {p}" for p in proven]
    lines += ["", f"Target role clusters: {', '.join(roles)}."]
    lines.append("Readiness, never certification - see `career gaps` for what is still open.")
    return "\n".join(lines)


def career(arg: str = "") -> str:
    """The `career` command: dispatch on the argument (mirrors `law <arg>`)."""
    a = (arg or "").strip().lower()
    try:
        if a in ("", "help", "sign"):
            return render_overview()
        if a == "checklist":
            return render_checklist()
        if a == "gaps":
            return render_gaps()
        if a == "evidence":
            return render_evidence()
        if a == "resume":
            return render_resume()
        if a.startswith("role"):
            return render_role(a.replace("role", "", 1).strip())
    except CareerError as exc:
        return f"Career board unavailable: {exc}"
    return (
        f"Unknown career view '{arg}'. Try: checklist · gaps · evidence · resume · "
        "role entry|intermediate|advanced"
    )
