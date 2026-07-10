"""CARD: pioneer -- Pioneer Mode: bold-but-honest engineering, surfaced in the MUD.

A disciplined pioneer challenges assumptions and proves unconventional solutions with
evidence -- bend convention, not truth/safety/trust. This command renders the framework
(doctrine, the Maverick Filter, the risk ladder, the constraint-review template) from
data/pioneer/risk_ladder.json, and lists the filed experiments in docs/pioneer_experiments/.
It gives the existing gates (VeritasGate, QualityGate, the Ritual) bold direction; it does
not replace them. See docs/pioneer_mode.md.
"""

from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_LADDER = _ROOT / "data" / "pioneer" / "risk_ladder.json"
_EXPERIMENTS = _ROOT / "docs" / "pioneer_experiments"


class PioneerError(Exception):
    """A malformed or missing risk-ladder data file -- fail loud, never render a lie."""


def load_ladder(path: Path | None = None) -> dict:
    """Load the risk-ladder data; a malformed file fails loud (a GATE)."""
    src = path or _LADDER
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PioneerError(f"unreadable risk ladder at {src}: {exc}") from exc
    ladder = data.get("risk_ladder")
    if not isinstance(ladder, dict) or "levels" not in ladder:
        raise PioneerError("risk ladder missing 'risk_ladder' / 'levels'")
    return ladder


def render_overview(ladder: dict | None = None) -> str:
    lad = ladder or load_ladder()
    lines = ["PIONEER MODE - bold, but honest", ""]
    lines += [f"  {d}" for d in lad.get("doctrine", [])]
    lines += ["", "  The Maverick Filter (recommend only if all hold):"]
    lines += [f"    - {q}" for q in lad.get("filter", [])]
    lines += [
        "",
        "  The pioneer does not ignore the instruments -- the pioneer reads them better.",
        "  views:  pioneer risks · pioneer plan · pioneer experiments   (see docs/pioneer_mode.md)",
    ]
    return "\n".join(lines)


def render_risks(ladder: dict | None = None) -> str:
    lad = ladder or load_ladder()
    lines = ["PIONEER MODE - the risk ladder", ""]
    for lv in lad["levels"]:
        lines.append(f"  L{lv['level']} {lv['name']} - {lv['meaning']}")
        lines.append(f"      e.g. {lv['examples']}")
        lines.append(f"      needs: {lv['needs']}")
    lines += ["", "  Higher levels need more proof; L4 needs a human + rollback; L5 is never."]
    return "\n".join(lines)


def render_plan(ladder: dict | None = None) -> str:
    lad = ladder or load_ladder()
    lines = [
        "PIONEER MODE - Constraint Review (fill this before a bold move)",
        "",
        "  Classify each constraint: hard · safety · legal/policy · quality · technical ·",
        "  resource · habit/assumption · unknown. Then answer:",
        "",
    ]
    lines += [f"  {q}" for q in lad.get("constraint_review_template", [])]
    return "\n".join(lines)


def render_experiments(root: Path | None = None) -> str:
    """List filed pioneer experiment reports (durable evidence, tracked in docs/)."""
    base = root or _EXPERIMENTS
    lines = ["PIONEER MODE - filed experiments (docs/pioneer_experiments/)", ""]
    reports = sorted(base.glob("*.md")) if base.is_dir() else []
    if not reports:
        lines.append("  (none filed yet -- run a bold experiment and file the report)")
        return "\n".join(lines)
    for r in reports:
        title = _first_title(r)
        lines.append(f"  - {r.stem}: {title}")
    lines += [
        "",
        f"  {len(reports)} filed. Each: hypothesis · constraint challenged · evidence · rollback.",
    ]
    return "\n".join(lines)


def _first_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def pioneer(arg: str = "") -> str:
    """The `pioneer` command: dispatch on the argument (mirrors `career`/`law`)."""
    a = (arg or "").strip().lower()
    try:
        if a in ("", "help"):
            return render_overview()
        if a == "risks":
            return render_risks()
        if a == "plan":
            return render_plan()
        if a in ("experiments", "next"):
            return render_experiments()
    except PioneerError as exc:
        return f"Pioneer Mode unavailable: {exc}"
    return f"Unknown pioneer view '{arg}'. Try: risks · plan · experiments"
