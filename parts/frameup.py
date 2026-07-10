"""CARD: frameup -- inspect the forge: an on-demand frame-up of the whole machine.

Composes the self-audit signals the project already produces -- registry validity, the QA
board, VeritasGate truth, documentation presence, the overclaim scan, plus the career and
pioneer systems -- into one green/yellow/red frame-up. It STORES nothing (computes from
filed state, like `pm status`) and REUSES the existing gates rather than duplicating them.

In the MUD: `inspect` (or `inspect forge`) renders the honest health of every major system
in one view. It gives the gates a single pane of glass; it does not replace them.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from parts.integrity import overclaim_hits, presence_gaps
from parts.qualitygate import FAIL, gate_all
from parts.registry import load_collective, validate
from parts.veritas import VERIFIED, truth_checks

_ROOT = Path(__file__).resolve().parent.parent
_WATCH = "watch"  # qualitygate uses a bare "watch" verdict (no exported constant)

GREEN = "green"
YELLOW = "yellow"
RED = "red"
_GLYPH = {GREEN: "🟢", YELLOW: "🟡", RED: "⛔"}


@dataclass(frozen=True)
class SystemFrame:
    """One system's line in the frame-up: its health and a one-line reading."""

    system: str
    verdict: str  # green | yellow | red
    detail: str
    gating: bool = True  # info-only rows (career/pioneer) never drag the overall down


def _career_line() -> SystemFrame:
    try:
        from parts.career import PARTIAL, PROVEN, load_board

        skills = [s for lvl in load_board()["levels"] for s in lvl["skills"]]
        c = Counter(s["status"] for s in skills)
        return SystemFrame(
            "career board",
            GREEN,
            f"{c.get(PROVEN, 0)} proven · {c.get(PARTIAL, 0)} partial · "
            f"{c.get('missing', 0)} missing (gaps tracked honestly)",
            gating=False,
        )
    except Exception as exc:  # pragma: no cover - defensive; a broken board shouldn't crash inspect
        return SystemFrame("career board", YELLOW, f"unavailable: {exc}", gating=False)


def _pioneer_line() -> SystemFrame:
    try:
        from parts.pioneer import _EXPERIMENTS

        n = len(list(_EXPERIMENTS.glob("*.md"))) if _EXPERIMENTS.is_dir() else 0
        return SystemFrame("pioneer mode", GREEN, f"{n} experiment(s) filed", gating=False)
    except Exception as exc:  # pragma: no cover
        return SystemFrame("pioneer mode", YELLOW, f"unavailable: {exc}", gating=False)


def frame_up(root: Path | None = None) -> list[SystemFrame]:
    """Gather every system's health, composed from the project's own gates. Computed live."""
    base = root or _ROOT
    recs = load_collective()

    problems = validate(recs) if recs else ["registry empty"]
    reg = SystemFrame(
        "classification registry",
        GREEN if not problems else RED,
        f"{len(recs)} objects filed, "
        + ("validates clean" if not problems else "; ".join(problems)),
    )

    board = Counter(r.verdict for r in gate_all(recs))
    qa_verdict = RED if board.get(FAIL) else (YELLOW if board.get(_WATCH) else GREEN)
    qa = SystemFrame(
        "quality gate (QA board)",
        qa_verdict,
        f"{board.get('pass', 0)} pass · {board.get(_WATCH, 0)} watch · {board.get(FAIL, 0)} fail",
    )

    checks = truth_checks(base)
    flagged = [c for c in checks if c.status != VERIFIED]
    truth = SystemFrame(
        "veritasgate (truth)",
        GREEN if not flagged else RED,
        "all claims verified"
        if not flagged
        else f"{len(flagged)} FLAGGED - correct before trusting",
    )

    gaps = presence_gaps(base)
    docs = SystemFrame(
        "documentation",
        GREEN if not gaps else YELLOW,
        "all key docs present" if not gaps else "MISSING: " + ", ".join(gaps),
    )

    over = overclaim_hits(base)
    overclaim = SystemFrame(
        "overclaim scan",
        GREEN if not over else RED,
        "no unqualified compliance/production claims" if not over else "FLAGS: " + ", ".join(over),
    )

    return [reg, qa, truth, docs, overclaim, _career_line(), _pioneer_line()]


def overall(frames: list[SystemFrame]) -> str:
    """Worst of the GATING systems wins; info-only rows never drag it down."""
    verdicts = {f.verdict for f in frames if f.gating}
    if RED in verdicts:
        return RED
    if YELLOW in verdicts:
        return YELLOW
    return GREEN


def render_frameup(root: Path | None = None) -> str:
    """The `inspect` projection: every system's health + one overall verdict."""
    frames = frame_up(root)
    ov = overall(frames)
    lines = [
        "THE FORGE - FRAME-UP INSPECTION",
        "",
        "  Composed live from the project's own gates (nothing stored, nothing faked).",
        "",
    ]
    for f in frames:
        lines.append(f"  {_GLYPH[f.verdict]} {f.system:<24} {f.detail}")
    lines += ["", f"  OVERALL: {_GLYPH[ov]} {ov.upper()}"]
    if ov == GREEN:
        lines.append("  Every system reads true. The forge is sound.")
    elif ov == YELLOW:
        lines.append("  Sound, with watch-items - see the yellow rows.")
    else:
        lines.append("  A red system needs attention before the forge is trusted.")
    return "\n".join(lines)


def inspect(arg: str = "") -> str:
    """The `inspect` command: render the frame-up. `inspect`, `inspect forge` -> the frame-up."""
    return render_frameup()
