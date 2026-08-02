"""CARD: hubble.autonomy -- how much authority the AI may exercise, gated by the situation.

RD-2026-0002 #13. `hubble.diagnosis` grades FINDINGS (is the change sound?); this governs the ACTOR
(how much may the AI do without a human?) -- a categorically different axis, from the Clinical
Workflow research's autonomy_mode. Three ascending modes:

    ASSISTANT  - propose only; a human performs every action.
    REVIEWER   - may prepare/stage a change; a human reviews and applies it.
    EXECUTOR   - may apply a change directly (still logged, still reversible).

A trigger table maps risky conditions to the MAXIMUM mode they allow: a security-sensitive change
caps at REVIEWER; acting on production without a tested rollback forbids EXECUTOR entirely; low
retrieval evidence, novel dependencies, and database migrations all pull authority down. The policy
never RAISES authority -- it only caps -- so the safe default wins when triggers conflict (the
Human-Keel rule: AI proposes, a human decides the risky calls).

Pure data + rules, stdlib only. `permits(requested, context)` answers yes/no + the reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Ascending authority. The index is the ordering; never reorder (callers compare by rank).
ASSISTANT, REVIEWER, EXECUTOR = "assistant", "reviewer", "executor"
_MODES = (ASSISTANT, REVIEWER, EXECUTOR)
_RANK = {m: i for i, m in enumerate(_MODES)}


class AutonomyError(ValueError):
    """Raised on an unknown mode or a malformed trigger."""


@dataclass(frozen=True)
class Trigger:
    """One condition and the maximum autonomy it permits while true (a cap, never a raise)."""

    condition: str  # a context flag name
    max_mode: str  # the highest mode allowed when this condition holds
    why: str

    def __post_init__(self) -> None:
        if self.max_mode not in _RANK:
            raise AutonomyError(f"trigger {self.condition!r}: unknown max_mode {self.max_mode!r}")


# The default policy (from the research's escalation-trigger list). Each caps authority; the lowest
# cap among the active triggers wins.
DEFAULT_TRIGGERS: tuple[Trigger, ...] = (
    Trigger(
        "production_without_tested_rollback",
        ASSISTANT,
        "acting on production without a tested rollback is never autonomous",
    ),
    Trigger("security_sensitive", REVIEWER, "security-sensitive changes need a human review"),
    Trigger("database_migration", REVIEWER, "a migration is irreversible-ish; a human applies it"),
    Trigger("low_evidence_grounding", REVIEWER, "thin retrieved evidence - a human should confirm"),
    Trigger("novel_dependency", REVIEWER, "a new/low-reputation dependency needs a human look"),
    Trigger("infrastructure_drift", REVIEWER, "infra drift detected - a human reconciles"),
)


@dataclass(frozen=True)
class AutonomyVerdict:
    """Whether a requested mode is permitted, the mode actually allowed, and the binding reasons."""

    requested: str
    permitted: bool
    allowed_mode: str  # the highest mode the context allows (<= requested when permitted)
    reasons: tuple[str, ...] = field(default_factory=tuple)


def max_allowed(
    context: set[str], triggers: tuple[Trigger, ...] = DEFAULT_TRIGGERS
) -> tuple[str, tuple[str, ...]]:
    """The highest mode the active context permits, and the reasons that capped it.

    context: the set of true condition flags. With no trigger active, EXECUTOR is allowed; each
    active trigger lowers the cap, and the lowest cap wins (safe default under conflict)."""
    cap = EXECUTOR
    reasons: list[str] = []
    for t in triggers:
        if t.condition in context and _RANK[t.max_mode] <= _RANK[cap]:
            if _RANK[t.max_mode] < _RANK[cap]:
                cap = t.max_mode
                reasons = [f"{t.condition} -> max {t.max_mode}: {t.why}"]
            else:  # equal cap from another trigger: record it too
                reasons.append(f"{t.condition} -> max {t.max_mode}: {t.why}")
    return cap, tuple(reasons)


def permits(
    requested: str, context: set[str], *, triggers: tuple[Trigger, ...] = DEFAULT_TRIGGERS
) -> AutonomyVerdict:
    """Answer whether the AI may act at `requested` authority given the context (yes/no + why).

    Permitted iff the requested mode is no higher than what the active triggers allow."""
    if requested not in _RANK:
        raise AutonomyError(f"unknown autonomy mode {requested!r}; choose {_MODES}")
    allowed, reasons = max_allowed(context, triggers)
    ok = _RANK[requested] <= _RANK[allowed]
    if ok:
        return AutonomyVerdict(requested, True, allowed, reasons or ("no triggers active",))
    return AutonomyVerdict(
        requested,
        False,
        allowed,
        reasons or (f"context caps authority at {allowed}",),
    )


def render(verdict: AutonomyVerdict) -> str:
    """A readable authority verdict (advisory; a human owns the risky call)."""
    head = "PERMITTED" if verdict.permitted else "DENIED"
    lines = [
        f"HUBBLE AUTONOMY -- {head}: requested {verdict.requested}, allowed {verdict.allowed_mode}"
    ]
    for r in verdict.reasons:
        lines.append(f"  - {r}")
    return "\n".join(lines)
