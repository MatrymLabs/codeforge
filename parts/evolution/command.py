"""CARD: evolution.command -- the read-only in-MUD window on the Blueprint Evolution Lab.

`evolution` shows what the lab has already produced; it NEVER runs a bake-off, promotes a
candidate, or writes anything. Producing a run is a separate authorized step (`make evolution`),
so the MUD can't trigger execution or repository change (per the report's command rules). This
is the read-only surface: list runs, show one run's report, explain the doctrine.
"""

from __future__ import annotations

from parts.evolution import store

_EXPLAIN = (
    "THE BLUEPRINT EVOLUTION LAB (nature-inspired, human-governed)\n"
    "  A design becomes a typed Blueprint Genome; a few hand-authored candidates are scored\n"
    "  by an evaluator swarm; hard gates run first, then weighted objectives (every metric\n"
    "  visible); failures become counterexamples. Nothing is promoted automatically -- a run\n"
    "  ends 'human_decision_required' and Josh selects the elite. This window is READ-ONLY:\n"
    "  produce a run with `make evolution`; nothing here executes or changes the repo.\n"
    "  Evidence + labels: docs/nature_inspired/research_mapping.md."
)


def _status() -> str:
    runs = store.list_runs()
    if not runs:
        return (
            "EVOLUTION LAB -- no runs recorded yet.\n"
            "  Produce one:  make evolution   (writes reports/evolution/<id>.json + .txt)\n"
            "  Then:         evolution show <id>   ·   evolution explain"
        )
    lines = ["EVOLUTION LAB -- recorded runs (read-only)", ""]
    for run_id in runs:
        summary = store.load_summary(run_id) or {}
        winner = summary.get("winner") or "(none qualified)"
        status = summary.get("final_status", "?")
        cxs = len(summary.get("counterexamples", []))
        lines.append(f"  {run_id:16} genome={summary.get('genome_id', '?'):14} top={winner}")
        lines.append(f"      status={status}   counterexamples={cxs}")
    lines.append("")
    lines.append("  evolution show <id>   ·   evolution explain")
    return "\n".join(lines)


def _show(run_id: str) -> str:
    if not run_id:
        return "Show which run? Try: evolution status"
    report = store.load_report(run_id)
    if report is None:
        return f"No recorded run '{run_id}'. Try: evolution status"
    return report.rstrip()


def evolution(arg: str = "") -> str:
    """The `evolution` command: dispatch a read-only view (mirrors `career` / `law`)."""
    a = (arg or "").strip()
    low = a.lower()
    if low in ("", "status", "list"):
        return _status()
    if low in ("explain", "nature", "help"):
        return _EXPLAIN
    if low in ("show", "compare") or low.startswith(("show ", "compare ")):
        parts = a.split(" ", 1)
        return _show(parts[1].strip() if len(parts) > 1 else "")
    return (
        f"Unknown evolution view '{arg}'. Try: status · show <id> · explain "
        "(runs are produced by `make evolution`, never from the MUD)."
    )
