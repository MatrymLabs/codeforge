"""Explicit capability-scoped authorization for Seed actions.

The policy is deliberately small and deny-first. Existing rank and owner checks remain
compatible; this module gives new contracts a single additive seam for role, capability,
scope, and audit-friendly refusal reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class PermissionDenied(ValueError):
    """The actor did not satisfy an explicit authorization requirement."""


@dataclass(frozen=True)
class PermissionContext:
    """Claims held by the authenticated actor for one request."""

    actor_id: str
    roles: frozenset[str] = frozenset()
    capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise PermissionDenied("actor_id must not be empty")


@dataclass(frozen=True)
class PermissionRule:
    """One allow/deny rule. Deny rules always win over allows."""

    capability: str
    scope: str = "*"
    actor_id: str = "*"
    effect: str = "allow"

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise PermissionDenied("rule capability must not be empty")
        if self.effect not in {"allow", "deny"}:
            raise PermissionDenied("rule effect must be allow or deny")


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class PermissionPolicy:
    """Authorize a required capability and optional role/scope."""

    rules: tuple[PermissionRule, ...] = ()
    default_allow: bool = False
    _audit: list[PermissionDecision] = field(default_factory=list, compare=False, repr=False)
    _revoked: set[tuple[str, str, str]] = field(default_factory=set, compare=False, repr=False)

    def decide(
        self,
        context: PermissionContext,
        *,
        capability: str,
        scope: str = "*",
        required_role: str = "",
    ) -> PermissionDecision:
        if not capability.strip():
            return self._record(PermissionDecision(True, "unprotected action"))
        if self.is_revoked(context, capability=capability, scope=scope):
            return self._record(PermissionDecision(False, f"policy revocation: {capability}"))
        if required_role and required_role not in context.roles:
            return self._record(PermissionDecision(False, f"missing role: {required_role}"))
        if capability not in context.capabilities:
            return self._record(PermissionDecision(False, f"missing capability: {capability}"))
        matching = [
            rule
            for rule in self.rules
            if rule.capability == capability
            and (rule.scope == "*" or rule.scope == scope)
            and (rule.actor_id == "*" or rule.actor_id == context.actor_id)
        ]
        if any(rule.effect == "deny" for rule in matching):
            return self._record(PermissionDecision(False, f"explicit denial: {capability}"))
        if matching or self.default_allow:
            return self._record(PermissionDecision(True, "authorized"))
        return self._record(PermissionDecision(False, f"no grant: {capability}"))

    def require(self, context: PermissionContext, **request: str) -> None:
        """Raise a deterministic, user-safe refusal when authorization fails."""
        decision = self.decide(context, **request)
        if not decision.allowed:
            raise PermissionDenied(decision.reason)

    def audit(self) -> tuple[PermissionDecision, ...]:
        """Return decisions made by this policy instance for diagnostics/tests."""
        return tuple(self._audit)

    def revoke(self, capability: str, *, scope: str = "*", actor_id: str = "*") -> None:
        """Revoke a capability grant for future checks on this policy instance.

        Revocation is intentionally explicit and scoped.  A running bounded operation checks the
        policy again when it returns, so a revocation cannot be mistaken for a successful
        authorization merely because the subprocess started before the revocation.
        """
        if not capability.strip():
            raise PermissionDenied("revoked capability must not be empty")
        self._revoked.add((capability.strip(), scope.strip() or "*", actor_id.strip() or "*"))

    def is_revoked(
        self,
        context: PermissionContext,
        *,
        capability: str,
        scope: str = "*",
    ) -> bool:
        """Return whether a matching capability revocation applies to this actor and scope."""
        return any(
            revoked_capability == capability
            and (revoked_scope == "*" or revoked_scope == scope)
            and (revoked_actor == "*" or revoked_actor == context.actor_id)
            for revoked_capability, revoked_scope, revoked_actor in self._revoked
        )

    def _record(self, decision: PermissionDecision) -> PermissionDecision:
        self._audit.append(decision)
        return decision
