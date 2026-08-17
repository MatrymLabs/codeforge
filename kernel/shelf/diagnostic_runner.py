"""CARD: diagnostic_runner -- decide proceed/revise/escalate/stop, with non-overridable escalation.

Clean-room from the Clinical Workflow research (differential-diagnosis + the
"non-overridable escalation classes" pattern, RS-2026-07-11-clinical p.6,13-14).
Instead of jumping to a fix, gather checks (static, security, sandbox, dependency,
grounding, ...) and decide an action from the weighted evidence. The safety
property: a FAILED check in an escalation class (security / sandbox / grounding)
forces escalate-or-stop, and NO confidence score can override it. This stops the
"looks fine, ship it" failure mode when a critical signal is red.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PROCEED = "proceed"
REVISE = "revise"
ESCALATE = "escalate"
STOP = "stop"

# a FAILED check of these kinds forces escalation regardless of the confidence score
DEFAULT_ESCALATION_CLASSES = frozenset({"security", "sandbox", "grounding"})
_SEVERITIES = frozenset({"info", "warning", "blocking"})


class DiagnosticError(ValueError):
    """Raised on a malformed check or threshold."""


@dataclass(frozen=True)
class Check:
    """One diagnostic signal."""

    name: str
    kind: str  # "static" | "security" | "sandbox" | "dependency" | "grounding" | ...
    passed: bool
    severity: str = "warning"  # info | warning | blocking
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.name:
            raise DiagnosticError("check name must be non-empty")  # noqa: TRY003
        if self.severity not in _SEVERITIES:
            raise DiagnosticError(f"severity must be one of {sorted(_SEVERITIES)}")  # noqa: TRY003
        if self.weight <= 0:
            raise DiagnosticError("weight must be > 0")  # noqa: TRY003


@dataclass(frozen=True)
class Verdict:
    decision: str  # proceed | revise | escalate | stop
    confidence: float
    escalated: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def decide(
    checks: list[Check],
    *,
    escalation_classes: frozenset[str] = DEFAULT_ESCALATION_CLASSES,
    proceed_threshold: float = 0.85,
    revise_threshold: float = 0.6,
) -> Verdict:
    """Decide an action from the checks. Escalation classes are non-overridable."""
    if not checks:
        raise DiagnosticError("decide needs at least one check")  # noqa: TRY003
    if not 0.0 <= revise_threshold <= proceed_threshold <= 1.0:
        raise DiagnosticError("need 0 <= revise_threshold <= proceed_threshold <= 1")  # noqa: TRY003

    failed = [c for c in checks if not c.passed]
    escalations = [c for c in failed if c.kind in escalation_classes]
    hard_stops = [c for c in failed if c.severity == "blocking"]

    total = sum(c.weight for c in checks)
    confidence = sum(c.weight for c in checks if c.passed) / total

    # 1. Non-overridable: a failed escalation-class check outranks any score.
    if escalations:
        blocking = [c for c in escalations if c.severity == "blocking"]
        reasons = tuple(f"{c.kind} check '{c.name}' failed (escalation class)" for c in escalations)
        return Verdict(STOP if blocking else ESCALATE, confidence, True, reasons)

    # 2. Any blocking failure (non-escalation class) stops too.
    if hard_stops:
        reasons = tuple(f"blocking check '{c.name}' failed" for c in hard_stops)
        return Verdict(STOP, confidence, False, reasons)

    # 3. Otherwise route by confidence.
    if confidence >= proceed_threshold:
        return Verdict(PROCEED, confidence, False, ())
    if confidence >= revise_threshold:
        weak = tuple(f"check '{c.name}' failed" for c in failed)
        return Verdict(
            REVISE, confidence, False, weak or ("confidence below the proceed threshold",)
        )
    return Verdict(
        STOP, confidence, False, (f"confidence {confidence:.2f} below the revise threshold",)
    )
