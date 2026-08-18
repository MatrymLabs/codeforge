"""CARD: risk_router -- score a change's risk and route the required review depth.

Clean-room from the FWA research (risk-based review routing, RS-2026-07-11-fwa
p.9,13). Ties oversight intensity to ACTUAL risk (what the change touches), not to
whether it "looks simple". A change that touches auth, secrets, migrations, CI, or
adds dependencies is routed to deeper review even if the diff is small; a trivial
change gets a light path. High-risk signals floor the band regardless of the score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LOW = "low"
MEDIUM = "medium"
HIGH = "high"
CRITICAL = "critical"


class RiskError(ValueError):
    """Raised on a malformed change."""


@dataclass(frozen=True)
class Change:
    """The risk-relevant signals of a proposed change."""

    files_touched: int = 1
    added_dependencies: int = 0
    scan_findings: int = 0
    touches_auth: bool = False  # authn / authz
    touches_secrets: bool = False
    touches_migrations: bool = False
    touches_ci_or_deploy: bool = False
    ai_authored: bool = False

    def __post_init__(self) -> None:
        for name in ("files_touched", "added_dependencies", "scan_findings"):
            if getattr(self, name) < 0:
                raise RiskError(f"{name} must be >= 0")


# signal -> (points, is a floor-to-HIGH signal)
_HIGH_FLOOR = ("touches_auth", "touches_secrets", "touches_migrations")


@dataclass(frozen=True)
class Routing:
    score: int  # 0..100
    band: str  # low | medium | high | critical
    required_approvals: int
    require_security_review: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def score(change: Change) -> int:
    """A 0..100 risk score from the change's signals."""
    pts = 0
    if change.touches_auth:
        pts += 30
    if change.touches_secrets:
        pts += 25
    if change.touches_migrations:
        pts += 25
    if change.touches_ci_or_deploy:
        pts += 20
    pts += min(change.added_dependencies, 4) * 10
    pts += min(change.scan_findings, 5) * 6
    if change.ai_authored:
        pts += 10
    pts += min(change.files_touched // 20, 1) * 5  # very large diffs add a little
    return min(pts, 100)


def route(
    change: Change,
    *,
    medium_at: int = 25,
    high_at: int = 50,
    critical_at: int = 80,
) -> Routing:
    """Route a change to a review band + required approvals from its risk."""
    if not 0 <= medium_at <= high_at <= critical_at <= 100:  # noqa: PLR2004
        raise RiskError("need 0 <= medium_at <= high_at <= critical_at <= 100")
    s = score(change)
    reasons: list[str] = []

    # high-risk signals floor the band, regardless of the numeric score.
    floored = [name for name in _HIGH_FLOOR if getattr(change, name)]
    for name in floored:
        reasons.append(f"{name.replace('_', ' ')} -> deeper review required")

    if s >= critical_at:
        band = CRITICAL
    elif s >= high_at or floored:
        band = HIGH
    elif s >= medium_at:
        band = MEDIUM
    else:
        band = LOW

    required_approvals = 2 if band in (HIGH, CRITICAL) else 1
    require_security_review = change.touches_auth or change.touches_secrets or band == CRITICAL
    if change.ai_authored:
        reasons.append("AI-authored change (disclosure logged, routed for a human read)")
    if not reasons:
        reasons.append(f"routine change (score {s})")
    return Routing(s, band, required_approvals, require_security_review, tuple(reasons))
