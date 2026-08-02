"""CARD: hubble.diagnosis -- differential diagnosis before intervention (the decision core).

Clinical diagnosis does not begin with treatment; it begins with a differential, evidence, and
risk triage. Hubble's decision core turns diagnostic findings (across static / security /
dependency / sandbox / retrieval-grounding dimensions) into ONE recommended action -- proceed,
revise, escalate, or stop -- with the confidence and reasons visible, so nothing hides behind a
single number. It advises; a human maintainer decides.

The load-bearing pattern is NOT the confidence formula: it is the NON-OVERRIDABLE escalation
classes. A failure in a high-risk dimension (security, sandbox, retrieval-grounding) forces
`escalate` regardless of how confident the rest of the panel looks -- the software analogue of
"consult the attending." High confidence can never buy past a security or sandbox failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Non-overridable escalation classes: a failure here forces `escalate`, whatever the confidence.
ESCALATION_CLASSES = frozenset({"security", "sandbox", "retrieval_grounding"})

# Below this confidence (and with no high-risk failure), the panel recommends revising, not
# proceeding -- reducing premature closure, a known failure mode in both diagnosis and debugging.
REVISE_BELOW = 0.75

PROCEED, REVISE, ESCALATE, STOP = "proceed", "revise", "escalate", "stop"


@dataclass(frozen=True)
class DiagnosticFinding:
    """One dimension's result in the panel: did it pass, how much does it weigh, and why."""

    dimension: str  # e.g. static | security | dependency | sandbox | retrieval_grounding
    passed: bool
    weight: float = 1.0
    note: str = ""


@dataclass(frozen=True)
class DiagnosticDecision:
    """The differential's verdict: confidence, the recommended action, and its reasons."""

    confidence: float  # 0.0..1.0, the weighted fraction of the panel that passed
    action: str  # proceed | revise | escalate | stop
    reasons: tuple[str, ...] = field(default_factory=tuple)
    escalation_class: str | None = None  # the high-risk dimension that forced escalation, if any


def decide(
    findings: list[DiagnosticFinding], *, revise_below: float = REVISE_BELOW
) -> DiagnosticDecision:
    """Recommend an action from the findings. Non-overridable escalation runs first, then
    confidence routes proceed / revise / stop. No finding set (empty) cannot proceed -> stop."""
    total_weight = sum(f.weight for f in findings) or 1.0
    achieved = sum(f.weight for f in findings if f.passed)
    confidence = achieved / total_weight
    reasons = tuple(f"{f.dimension}: {f.note or 'failed'}" for f in findings if not f.passed)

    # Non-overridable: any high-risk failure escalates, however confident the rest looks.
    high_risk = [f for f in findings if not f.passed and f.dimension in ESCALATION_CLASSES]
    if high_risk:
        return DiagnosticDecision(
            confidence=confidence,
            action=ESCALATE,
            reasons=reasons or ("high-risk failure detected",),
            escalation_class=high_risk[0].dimension,
        )
    if not findings or confidence == 0.0:
        return DiagnosticDecision(confidence, STOP, reasons or ("no diagnostic evidence",))
    if confidence < revise_below:
        return DiagnosticDecision(confidence, REVISE, reasons or ("confidence below threshold",))
    return DiagnosticDecision(confidence, PROCEED, ("all critical checks passed",))


def render_decision(findings: list[DiagnosticFinding], decision: DiagnosticDecision) -> str:
    """A readable differential: every finding, the confidence, and the recommended action."""
    lines = [
        "HUBBLE DIAGNOSIS -- differential before intervention",
        f"  confidence: {decision.confidence:.2f}   action: {decision.action.upper()}",
    ]
    if decision.escalation_class:
        lines.append(f"  ! non-overridable escalation: {decision.escalation_class} failed")
    lines.append("")
    lines.append("FINDINGS")
    for f in findings:
        mark = "[x]" if f.passed else "[ ]"
        risk = " (high-risk)" if f.dimension in ESCALATION_CLASSES else ""
        lines.append(f"  {mark} {f.dimension}{risk}  w={f.weight:g}")
        if not f.passed and f.note:
            lines.append(f"        -> {f.note}")
    lines += [
        "",
        f"RECOMMENDATION: {decision.action.upper()} -- advisory; a human maintainer decides.",
    ]
    return "\n".join(lines)
