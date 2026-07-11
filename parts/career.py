"""CARD: career -- the Career Evidence Sign: map CodeForge work to job-ready skills.

A data-driven proof board. It reads data/career/career_evidence_matrix.json (grounded in
BLS/O*NET research) and renders, per level, each skill with the exact repo artifact that
proves it -- and the honest gaps. It never says "job-ready"; it says "here is the skill,
here is the proof, here is what is missing."

VeritasGate rule, enforced here: a skill marked `proven` or `partial` must cite at least
one repo path that actually exists. `unproven_claims()` finds violations; the test twin
pins that the shipped board has none, so the sign cannot quietly overclaim.

Second axis -- the human keel (Human Keel Doctrine, docs/human_keel_doctrine.md): each skill
may carry an `ownership` block (level 0-5 + a keel line + a backing record). A skill can be
`proven` yet ownership `undeclared`. KeelGate rule: a claim of level >= DEFENDABLE must cite
a real keel record; `ownership_gaps()` finds violations and the test twin pins zero.
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

# --- The ownership axis (Human Keel Doctrine) --------------------------------------------
# Orthogonal to evidence: a skill can be `proven` (its artifact exists) yet ownership
# `undeclared` (Josh has not yet claimed or defended it). Levels are the Ownership Gate.
# See docs/human_keel_doctrine.md.
_OWNERSHIP_NAMES = {
    0: "ai_output",
    1: "reviewed",
    2: "verified",
    3: "modified",
    4: "defendable",
    5: "extended",
}
DEFENDABLE = 4  # level at/above which ownership is a portfolio claim needing a keel record


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
            _validate_ownership(skill)
    return board


def _validate_ownership(skill: dict) -> None:
    """Ownership is optional, but a present block must be well formed (a GATE).

    An absent block means `undeclared` -- honest, not an error. A malformed one fails loud
    so the ownership axis can never be quietly corrupt.
    """
    own = skill.get("ownership")
    if own is None:
        return
    if not isinstance(own, dict) or "level" not in own:
        raise CareerError(f"skill {skill['skill_id']}: ownership must be a mapping with a 'level'")
    level = own["level"]
    if not isinstance(level, int) or isinstance(level, bool) or level not in _OWNERSHIP_NAMES:
        raise CareerError(
            f"skill {skill['skill_id']}: ownership level must be an int 0-5, got {level!r}"
        )


def _skills(board: dict) -> list[dict]:
    return [s for lvl in board["levels"] for s in lvl.get("skills", [])]


def skill_label(skill_id: str, board: dict | None = None) -> str | None:
    """The display name for a skill_id, or None if the board has no such skill.
    A public lookup so other systems (the Classroom) can name a skill honestly."""
    b = board or load_board()
    for s in _skills(b):
        if s["skill_id"] == skill_id:
            return s["skill"]
    return None


def ownership_name(level: int) -> str:
    """The Ownership Gate name for a level (e.g. 2 -> 'verified')."""
    return _OWNERSHIP_NAMES.get(level, "?")


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


def ownership_gaps(board: dict, root: Path | None = None) -> list[str]:
    """KeelGate: skills whose ownership claim overreaches its evidence.

    A skill claiming level >= DEFENDABLE (portfolio ownership) must carry a non-empty `keel`
    line AND a `record` path that exists on disk. An empty list means no ownership claim
    outruns its written record. Undeclared ownership is NOT a violation -- it is an honest
    gap, surfaced by the view, never by this gate.
    """
    base = root or _ROOT
    bad: list[str] = []
    for s in _skills(board):
        own = s.get("ownership")
        if not own or own["level"] < DEFENDABLE:
            continue
        keel = str(own.get("keel", "")).strip()
        record = str(own.get("record", "")).strip()
        if not keel:
            bad.append(f"{s['skill_id']} (level {own['level']}) -- claims defendable, no keel line")
        elif not record or not (base / record).exists():
            bad.append(
                f"{s['skill_id']} (level {own['level']}) -- keel record does not exist: {record!r}"
            )
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
        "  views:  career checklist · career gaps · career evidence · career ownership",
        "          career resume · career role entry|intermediate|advanced",
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


def render_ownership(board: dict | None = None, demonstrated: dict[str, int] | None = None) -> str:
    """The human keel: how deeply Josh OWNS each skill, orthogonal to whether its artifact
    exists. Three states per skill: `declared` (in the git-tracked matrix, KeelGate-guarded),
    `demonstrated` (unlocked in the Classroom, not yet made durable), and `undeclared` (an
    honest gap). Declared always outranks demonstrated for the same skill."""
    b = board or load_board()
    demo = demonstrated or {}
    skills = _skills(b)
    lines = [
        "CAREER EVIDENCE SIGN - OWNERSHIP (the human keel)",
        "",
        "If AI replaces every plank, the keel stays human. This axis records what Josh",
        "personally decided and can defend -- separate from whether the artifact exists.",
        "  legend: 0 ai_output · 1 reviewed · 2 verified · 3 modified · 4 defendable · 5 extended",
        "",
    ]
    declared = [s for s in skills if s.get("ownership")]
    for s in declared:
        own = s["ownership"]
        level = own["level"]
        lines.append(f"  [{level} {_OWNERSHIP_NAMES[level]}] {s['skill']}   (declared)")
        if own.get("keel"):
            lines.append(f"      keel:   {own['keel']}")
        if own.get("record"):
            lines.append(f"      record: {own['record']}")
        lines.append("")
    # Demonstrated: earned in the Classroom, not yet declared. Declared wins if both exist.
    shown = [s for s in skills if not s.get("ownership") and s["skill_id"] in demo]
    for s in shown:
        level = demo[s["skill_id"]]
        lines.append(
            f"  [{level} {_OWNERSHIP_NAMES.get(level, '?')}] {s['skill']}   (demonstrated)"
        )
        lines.append(
            f"      earned in the Classroom - make it durable:  career claim {s['skill_id']}"
        )
        lines.append("")
    undeclared = [s for s in skills if not s.get("ownership") and s["skill_id"] not in demo]
    if undeclared:
        lines.append("  UNDECLARED (proof may exist; ownership not yet claimed):")
        for s in undeclared:
            lines.append(f"    [-] {s['skill']}")
        lines.append("")
    lines += [
        f"  declared {len(declared)} · demonstrated {len(shown)} · undeclared {len(undeclared)} "
        f"of {len(skills)} skills",
        "  Undeclared ownership is an honest gap, not a claim - Josh claims each as he",
        "  defends it. Level 4+ requires a real keel record (KeelGate).",
    ]
    return "\n".join(lines)


def render_claim(
    skill_id: str, board: dict | None = None, demonstrated: dict[str, int] | None = None
) -> str:
    """Bridge a Classroom-demonstrated unlock into a durable, human-committed declaration.

    Prints the exact `ownership` JSON block for Josh to paste into the matrix and commit
    himself. The Classroom NEVER writes the matrix; this only proposes the edit. Level 4+
    (portfolio-ready) is refused here -- that needs a written keel record, not a lesson."""
    b = board or load_board()
    demo = demonstrated or {}
    skill_id = skill_id.strip()
    label = skill_label(skill_id, b)
    if label is None:
        return f"No such skill '{skill_id}'. See: career ownership"
    if skill_id not in demo:
        return (
            f"'{label}' is not demonstrated yet. Earn it first in the Classroom "
            f"(lesson list), then: career claim {skill_id}"
        )
    level = demo[skill_id]
    record = _lesson_record_for(skill_id)
    block = (
        '      "ownership": {\n'
        f'        "level": {level},\n'
        f'        "keel": "<one line: what you can now explain and defend about this>",\n'
        f'        "record": "{record}"\n'
        "      }"
    )
    return (
        f"CLAIM: {label}  ({skill_id})  ->  level {level} {_OWNERSHIP_NAMES.get(level, '?')}\n\n"
        "You demonstrated this in the Classroom. To make it a durable, owned claim, add the\n"
        "block below to this skill in data/career/career_evidence_matrix.json and commit it\n"
        "yourself (the Classroom never writes the board for you):\n\n"
        f"{block}\n\n"
        "Level 4 (defendable / portfolio-ready) is not granted by a lesson - it needs a\n"
        "written keel record and your own defense (see docs/human_keel_doctrine.md)."
    )


def _lesson_record_for(skill_id: str) -> str:
    """The real lesson file that proves this skill, as a provenance path for a claim block
    (or a placeholder if none is found). Read-only; imports lazily to avoid an import cycle."""
    from parts.assessment import _default_lessons_dir, load_lesson

    lessons_dir = _default_lessons_dir()
    if lessons_dir.is_dir():
        for path in sorted(lessons_dir.glob("*.yaml")):
            if load_lesson(path).proves_skill == skill_id:
                return f"lessons/{path.name}"
    return "<path to the artifact that proves this>"


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


def career(arg: str = "", demonstrated: dict[str, int] | None = None) -> str:
    """The `career` command: dispatch on the argument (mirrors `law <arg>`).

    `demonstrated` (skill_id -> level) is the caller's per-player Classroom unlocks, injected
    by the tick so the board can show demonstrated ownership beside declared, and so
    `career claim` can propose a durable claim. None means "no player context / none earned."
    """
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
        if a == "ownership":
            return render_ownership(demonstrated=demonstrated)
        if a.startswith("claim"):
            return render_claim(arg[len("claim") :].strip(), demonstrated=demonstrated)
        if a == "resume":
            return render_resume()
        if a.startswith("role"):
            return render_role(a.replace("role", "", 1).strip())
    except CareerError as exc:
        return f"Career board unavailable: {exc}"
    return (
        f"Unknown career view '{arg}'. Try: checklist · gaps · evidence · ownership · claim · "
        "resume · role entry|intermediate|advanced"
    )
