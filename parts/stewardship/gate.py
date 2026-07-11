"""CARD: stewardship.gate -- the Stewardship Gate: is this change eligible to merge?

The executable heart of the FWA doctrine ("make policies executable"). It composes a change's
already-computed signals into ONE verdict: hard gates first (tests pass, no blocking SAST, no
secrets, dependencies admitted, AI involvement disclosed), then risk-routed human approval.
Every check is visible, so the verdict never hides why it passed or blocked. It NEVER re-runs a
scan (it reads what the change already proved) and NEVER auto-merges: it advises; a human and CI
branch protection still decide. This mirrors the report's `verify_change` gate, adapted to what
CodeForge can actually verify today (provenance/attestation are a later slice).
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.stewardship.change import ChangeDescriptor
from parts.stewardship.risk import RiskAssessment, assess_risk

PASS, FAIL = "pass", "fail"


@dataclass(frozen=True)
class CheckResult:
    """One assurance check's verdict on a change, with the reason it failed (empty if passed)."""

    check_id: str
    requirement: str
    status: str  # pass | fail
    blocking: bool
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    """A change's merge eligibility: the risk, every check, and what approval it still needs."""

    change_id: str
    eligible: bool
    risk: RiskAssessment
    checks: tuple[CheckResult, ...]
    required_approvals: int
    human_approvals: int


def _check(cid: str, req: str, ok: bool, detail: str) -> CheckResult:
    return CheckResult(cid, req, PASS if ok else FAIL, blocking=True, detail="" if ok else detail)


def verify_change(change: ChangeDescriptor) -> Verdict:
    """Compose the change's signals into a visible merge-eligibility verdict (hard gates first,
    then risk-routed approval). Blocking failures make it ineligible; nothing merges here."""
    risk = assess_risk(change)
    deps_ok = (not change.dependencies_added) or change.dependencies_approved
    checks = (
        _check(
            "FWA01", "required tests passed", change.tests_passed, "the required tests did not pass"
        ),
        _check(
            "FWA02",
            "no blocking static-analysis findings",
            change.sast_blocking_findings == 0,
            f"{change.sast_blocking_findings} blocking SAST finding(s)",
        ),
        _check(
            "FWA03",
            "no secrets in the change",
            change.secrets_findings == 0,
            f"{change.secrets_findings} secret finding(s)",
        ),
        _check(
            "FWA04",
            "all added dependencies admitted",
            deps_ok,
            f"unadmitted dependency: {', '.join(change.dependencies_added)}",
        ),
        _check(
            "FWA05",
            "AI involvement disclosed",
            change.ai_assisted is not None,
            "ai_assisted is undisclosed (must be explicitly True or False)",
        ),
        _check(
            "FWA06",
            f"{risk.tier}-risk change has {risk.required_approvals} approval(s)",
            change.human_approvals >= risk.required_approvals,
            f"needs {risk.required_approvals} human approval(s), has {change.human_approvals}",
        ),
    )
    eligible = not any(c.status == FAIL and c.blocking for c in checks)
    return Verdict(
        change.change_id, eligible, risk, checks, risk.required_approvals, change.human_approvals
    )


def blocking_reasons(verdict: Verdict) -> list[str]:
    """The requirements that blocked this change (empty when eligible)."""
    return [f"{c.check_id}: {c.detail}" for c in verdict.checks if c.status == FAIL and c.blocking]


def render_verdict(verdict: Verdict) -> str:
    """A readable Stewardship Gate report: risk, every check, and the eligibility verdict."""
    r = verdict.risk
    lines = [
        f"STEWARDSHIP GATE -- change {verdict.change_id}",
        f"  risk: {r.tier.upper()} ({r.score}/100)   "
        f"approvals: {verdict.human_approvals}/{r.required_approvals}",
    ]
    for factor in r.factors:
        lines.append(f"    ! {factor}")
    lines.append("")
    lines.append("CHECKS")
    for c in verdict.checks:
        mark = "[x]" if c.status == PASS else "[ ]"
        lines.append(f"  {mark} {c.check_id} {c.requirement}")
        if c.status == FAIL:
            lines.append(f"        -> {c.detail}")
    lines += [
        "",
        f"VERDICT: {'ELIGIBLE' if verdict.eligible else 'BLOCKED'}"
        f" -- advisory; a human and CI branch protection still decide, nothing auto-merges.",
    ]
    return "\n".join(lines)
