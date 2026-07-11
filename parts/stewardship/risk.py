"""CARD: stewardship.risk -- the RiskRouter: score a change, route the review depth.

Oversight intensity should track RISK, not whether a change "looks simple" (the FWA report's
governance-bypass warning: AI-authored PRs can look small while touching security-critical
surfaces). A change that touches a security surface, adds a dependency, or is AI-authored on a
sensitive path earns more scrutiny; a trivial low-risk change is not taxed at all. Every risk
factor that fires is recorded, so the score never hides its reasons.
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.stewardship.change import ChangeDescriptor

# Path prefixes whose change carries security blast radius. Touching any of these raises the
# risk tier (and thus the required review depth): auth/authz, persistence, secrets/config, CI
# workflows, and the network gateways.
SECURITY_SURFACES: dict[str, tuple[str, ...]] = {
    "auth/authorization": ("parts/accounts.py", "parts/ranks.py"),
    "persistence": ("parts/db.py", "migrations/"),
    "secrets/config": (".env", ".secrets.baseline", "pyproject.toml"),
    "ci/workflows": (".github/workflows/",),
    "network/gateway": ("parts/gateway.py", "parts/web_gateway.py", "parts/api.py"),
}

# Review depth by risk tier: low-risk work is NOT taxed (0 extra approvals); high-risk work is
# review-heavy (2), per the report's "risk >= high => >= 2 human approvals".
_TIERS = ((70, "high", 2), (30, "medium", 1), (0, "low", 0))


@dataclass(frozen=True)
class RiskAssessment:
    """A change's risk: a 0-100 score, its tier, the approvals it needs, and WHY it scored so."""

    score: int
    tier: str  # low | medium | high
    required_approvals: int
    factors: tuple[str, ...]  # the risk reasons that fired (visible, never hidden)


def touched_surfaces(files: tuple[str, ...]) -> list[str]:
    """The named security surfaces this change touches (empty if none)."""
    hits: list[str] = []
    for name, prefixes in SECURITY_SURFACES.items():
        if any(f == p or f.startswith(p) for f in files for p in prefixes):
            hits.append(name)
    return hits


def assess_risk(change: ChangeDescriptor) -> RiskAssessment:
    """Score the change 0-100 from visible factors, then route it to a review tier."""
    score = 0
    factors: list[str] = []
    surfaces = touched_surfaces(change.files_touched)
    if surfaces:
        score += 40
        factors.append(f"touches security surface(s): {', '.join(surfaces)}")
    if change.dependencies_added:
        score += 25
        factors.append(f"adds dependency: {', '.join(change.dependencies_added)}")
    if change.ai_assisted and surfaces:
        score += 25
        factors.append("AI-authored change on a security surface")
    if change.sast_blocking_findings or change.secrets_findings:
        score += 20
        factors.append("static-analysis or secret findings present")
    score = min(score, 100)
    tier, approvals = next((t, a) for floor, t, a in _TIERS if score >= floor)
    return RiskAssessment(score, tier, approvals, tuple(factors))
