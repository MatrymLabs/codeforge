"""CARD: pm -- the project control panel. Composes registry + QualityGate.

The PM layer never stores a second copy of the project state -- it COMPUTES it from
what's already filed. `pm status` reads the registry (a part) and runs the
QualityGate (a part) and reports readiness metrics: objects filed, QA pass/watch/
fail, docs gaps, built vs planned. Part + part + part = a live dashboard. Readiness
only; no dates or milestones are invented -- the narrative plan lives in
docs/project_management.md.
"""

from dataclasses import dataclass, field

from parts.qualitygate import FAIL, PASS, gate_all
from parts.registry import load_collective


@dataclass
class ProjectMetrics:
    """The project's state, derived (not stored) from the registry + the QA gate."""

    total: int
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    qa_pass: int = 0
    qa_watch: int = 0
    qa_fail: int = 0
    docs_missing: int = 0
    built: int = 0
    planned: int = 0  # prototypes -- filed but not yet built


def project_metrics() -> ProjectMetrics:
    """Compute the project dashboard by composing the registry and the QualityGate."""
    records = load_collective()
    results = gate_all(records)
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for r in records:
        by_type[r.type] = by_type.get(r.type, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
    metrics = ProjectMetrics(
        total=len(records),
        by_type=by_type,
        by_status=by_status,
        built=sum(1 for r in records if r.status != "prototype"),
        planned=sum(1 for r in records if r.status == "prototype"),
    )
    for result in results:
        if result.verdict == PASS:
            metrics.qa_pass += 1
        elif result.verdict == FAIL:
            metrics.qa_fail += 1
        else:
            metrics.qa_watch += 1
        if any(c.check_id == "QG04" and c.result == FAIL for c in result.checks):
            metrics.docs_missing += 1
    return metrics


def _recommended_next(m: ProjectMetrics) -> str:
    if m.qa_fail:
        return f"Fix {m.qa_fail} failing object(s) -- run `qa gate all` to see the gaps."
    if m.docs_missing:
        return f"Link docs on {m.docs_missing} object(s) to raise them from watch to pass."
    if m.planned:
        return f"Build the next of {m.planned} planned (prototype) object(s)."
    return "All filed objects pass -- pick the next milestone in docs/project_management.md."


def pm_metrics(metrics: ProjectMetrics | None = None) -> str:
    """Raw counts, honestly computed. `metrics` is injectable for deterministic tests."""
    m = metrics if metrics is not None else project_metrics()
    types = ", ".join(f"{n} {t}" for t, n in sorted(m.by_type.items()))
    return "\n".join(
        [
            "CodeForge Metrics (computed from the registry + QualityGate):",
            f"  Objects filed:   {m.total}   ({types})",
            f"  Built / planned: {m.built} built, {m.planned} planned (prototype)",
            f"  QA readiness:    {m.qa_pass} pass, {m.qa_watch} watch, {m.qa_fail} fail",
            f"  Docs gaps:       {m.docs_missing} object(s) missing a docs link (QG04)",
        ]
    )


def pm_status(metrics: ProjectMetrics | None = None) -> str:
    """The project status report -- the dashboard, plus the recommended next action.
    `metrics` is injectable so the red/green gate logic is deterministically testable."""
    m = metrics if metrics is not None else project_metrics()
    ready_pct = round(100 * m.qa_pass / m.total) if m.total else 0
    color = (
        "green"
        if m.qa_fail == 0 and m.docs_missing == 0
        else ("yellow" if m.qa_fail == 0 else "red")
    )
    return "\n".join(
        [
            "CodeForge Project Status",
            "",
            f"Overall: {color.upper()}  ({m.qa_pass}/{m.total} objects pass QA, {ready_pct}%)",
            f"Filed:   {m.total} objects  ({m.built} built, {m.planned} planned)",
            f"QA:      {m.qa_pass} pass · {m.qa_watch} watch · {m.qa_fail} fail",
            f"Docs:    {m.docs_missing} object(s) need a docs link",
            "",
            f"Recommended next: {_recommended_next(m)}",
            "",
            "Plan, milestones, risks, and the backlog: docs/project_management.md",
        ]
    )
