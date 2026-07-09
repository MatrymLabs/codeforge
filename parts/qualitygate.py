"""CARD: qualitygate -- the Safety + QA spine. Composes with the registry.

Proof of the engine: a QualityGate is a PART that plugs into the registry PART.
`qa gate all` reads every filed designation (the registry) and grades each one (this
card) -- part + part = a self-audit. SafetyReview rates risk; docs_check sweeps the
key docs. Nothing here claims compliance: it reports READINESS, honestly, with
evidence paths. OSHA-informed, never OSHA-certified; maturity is never assumed.
"""

from dataclasses import dataclass, field
from pathlib import Path

from parts.registry import Designation, load_collective

_ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, NA = "pass", "fail", "n/a"

# --- Quality gate -----------------------------------------------------------


@dataclass(frozen=True)
class GateCheck:
    """One requirement's verdict, with the evidence that proves (or fails) it."""

    check_id: str
    requirement: str
    result: str  # pass | fail | n/a
    evidence: str = ""
    notes: str = ""


@dataclass
class GateResult:
    """A whole object's readiness: pass (ready), watch (soft gap), fail (hard gap)."""

    designation: str
    object_type: str
    declared_status: str
    verdict: str  # pass | watch | fail
    checks: list[GateCheck] = field(default_factory=list)


def run_gate(record: Designation, root: Path | None = None) -> GateResult:
    """Grade one filed object against the readiness checklist (read-only)."""
    base = root if root is not None else _ROOT

    def exists(rel: str) -> bool:
        return bool(rel) and (base / rel).exists()

    proto = record.status == "prototype"
    checks: list[GateCheck] = []

    checks.append(
        GateCheck(
            "QG01",
            "Has a clear purpose",
            PASS if record.function.strip() else FAIL,
            notes="" if record.function.strip() else "function is empty",
        )
    )
    if proto:
        checks.append(GateCheck("QG02", "Source file exists", NA, notes="prototype -- not built"))
        checks.append(GateCheck("QG03", "Has tests", NA, notes="prototype -- not built"))
    else:
        src = exists(record.file)
        checks.append(
            GateCheck(
                "QG02",
                "Source file exists",
                PASS if src else FAIL,
                evidence=record.file if src else "",
                notes="" if src else f"missing: {record.file}",
            )
        )
        tst = exists(record.tests)
        checks.append(
            GateCheck(
                "QG03",
                "Has tests",
                PASS if tst else FAIL,
                evidence=record.tests if tst else "",
                notes="" if tst else "no tests filed",
            )
        )
    doc_ok = exists(record.docs) or bool(record.notes.strip())
    checks.append(
        GateCheck(
            "QG04",
            "Has documentation",
            PASS if doc_ok else FAIL,
            evidence=record.docs,
            notes="" if doc_ok else "no docs path or notes",
        )
    )
    if record.status in ("active", "hardened"):
        supported = exists(record.file) and exists(record.tests)
        checks.append(
            GateCheck(
                "QG05",
                f"Evidence supports declared '{record.status}'",
                PASS if supported else FAIL,
                notes="" if supported else "declared built but file or tests missing",
            )
        )
    else:
        checks.append(GateCheck("QG05", "Maturity declared", PASS, evidence=record.status))

    hard = {"QG02", "QG03", "QG05"}
    soft = {"QG01", "QG04"}
    verdict = (
        FAIL
        if any(c.result == FAIL and c.check_id in hard for c in checks)
        else ("watch" if any(c.result == FAIL and c.check_id in soft for c in checks) else PASS)
    )
    return GateResult(record.designation, record.type, record.status, verdict, checks)


def gate_all(
    records: list[Designation] | None = None, root: Path | None = None
) -> list[GateResult]:
    """Run the gate over the whole collective -- the self-audit (part + part)."""
    recs = records if records is not None else load_collective()
    return [run_gate(r, root) for r in recs]


# --- Safety review ----------------------------------------------------------


@dataclass
class SafetyFinding:
    """A risk assessment for one object. High/critical need human approval."""

    designation: str
    risk_level: str  # low | medium | high | critical
    categories: list[str]
    approval_required: bool
    notes: str


def safety_review(record: Designation) -> SafetyFinding:
    """Rate an object's risk from its type/tags (heuristic, honest, read-only)."""
    categories: list[str] = []
    notes: list[str] = []
    risk = "low"
    approval = False
    is_admin = record.type == "CMD" and (record.label.startswith("@") or "admin" in record.tags)
    if is_admin or record.type == "SYS":
        risk, approval = "medium", True
        categories.append("unsafe_command_execution")
        notes.append("admin/system capability -- rank-gated; approval enforced by min_rank")
    if record.type == "ITM":
        categories.append("broken_player_progression")
        notes.append("spawns into world state; the instance is transient")
    if record.status == "prototype":
        categories.append("untested_behavior")
        notes.append("prototype -- not built or tested yet")
    if not categories:
        categories.append("none_identified")
        notes.append("read-only / low blast radius")
    return SafetyFinding(record.designation, risk, categories, approval, "; ".join(notes))


# --- Documentation impact sweep --------------------------------------------

_KEY_DOCS = (
    ("README.md", "project overview"),
    ("CHANGELOG.md", "behavior changes"),
    ("SECURITY.md", "security policy"),
    ("CONTRIBUTING.md", "how to contribute"),
    ("docs/architecture.md", "architecture"),
    ("docs/safety_qa_system.md", "safety + QA system"),
    ("docs/classification/CLASSIFICATION_SYSTEM.md", "classification registry"),
)


def docs_check(root: Path | None = None) -> str:
    """DocumentationImpactSweep: which key docs exist, which are missing (read-only)."""
    base = root if root is not None else _ROOT
    lines = ["Documentation Impact Sweep:", ""]
    missing = 0
    for rel, why in _KEY_DOCS:
        ok = (base / rel).exists()
        if not ok:
            missing += 1
        lines.append(f"  {'PRESENT' if ok else 'MISSING'}  {rel:46}({why})")
    lines.append("")
    lines.append(f"{missing} key doc(s) missing." if missing else "All key docs present.")
    return "\n".join(lines)


# --- Renderers (the projections the commands show) --------------------------


def _find(designation: str) -> Designation | None:
    low = designation.strip().lower()
    return next((r for r in load_collective() if r.designation.lower() == low), None)


def render_gate(designation: str) -> str:
    record = _find(designation)
    if record is None:
        return f"No object '{designation}'. Try `registry list` or `qa gate all`."
    result = run_gate(record)
    lines = [
        f"QualityGate: {result.designation}  ({result.object_type}, {result.declared_status})",
        f"Verdict: {result.verdict.upper()}",
        "",
    ]
    for c in result.checks:
        tail = f" -- {c.notes}" if c.notes else (f" [{c.evidence}]" if c.evidence else "")
        lines.append(f"  [{c.result:4}] {c.check_id} {c.requirement}{tail}")
    return "\n".join(lines)


def render_gate_all() -> str:
    results = gate_all()
    tally = {PASS: 0, "watch": 0, FAIL: 0}
    for r in results:
        tally[r.verdict] += 1
    lines = [
        "CodeForge Readiness: qa gate all",
        f"{len(results)} object(s) audited -- "
        f"{tally[PASS]} pass, {tally['watch']} watch, {tally[FAIL]} fail.",
        "",
    ]
    for r in sorted(
        results, key=lambda x: (x.verdict != FAIL, x.verdict != "watch", x.designation)
    ):
        if r.verdict != PASS:
            gap = ", ".join(c.check_id for c in r.checks if c.result == FAIL)
            lines.append(f"  {r.verdict.upper():5} {r.designation:26} (gaps: {gap})")
    if all(r.verdict == PASS for r in results):
        lines.append("  All objects pass. The workshop is ready.")
    else:
        lines.append("\n`qa gate <designation>` for one object's checklist.")
    return "\n".join(lines)


def render_safety(designation: str) -> str:
    record = _find(designation)
    if record is None:
        return f"No object '{designation}'. Try `registry list`."
    finding = safety_review(record)
    approval = "REQUIRED (human)" if finding.approval_required else "not required"
    return "\n".join(
        [
            f"SafetyReview: {finding.designation}",
            f"Risk level: {finding.risk_level.upper()}",
            f"Categories: {', '.join(finding.categories)}",
            f"Approval: {approval}",
            f"Notes: {finding.notes}",
            "",
            "Readiness only -- no compliance/OSHA/legal claim is made.",
        ]
    )
