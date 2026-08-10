"""The platform identity carried by every protected Seed request.

World-account identity answers who a player is inside a world. ``SessionIdentity`` answers which
authenticated principal is exercising which authority against which Seed. Keeping those concepts
separate prevents a client-side player name or a Seed owner field from becoming authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from kernel.permission_policy import PermissionContext

PrincipalKind = Literal["human", "agent", "service", "tool"]
_PRINCIPAL_KINDS = frozenset({"human", "agent", "service", "tool"})


class SessionIdentityError(ValueError):
    """The platform identity is malformed or cannot exercise the requested Seed scope."""


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SessionIdentityError(f"{field} must be a non-empty string")
    return value.strip()


def _as_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None:
        raise SessionIdentityError(f"{field} must include a timezone")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class SessionIdentity:
    """Authenticated authority for one request scope.

    The Seed runtime is authoritative for this record. A client may display it, but cannot mint,
    widen, or substitute the principal, Seed, capabilities, or expiry.
    """

    principal_id: str
    principal_kind: PrincipalKind
    session_id: str
    seed_id: str
    issued_at: datetime
    expires_at: datetime
    correlation_id: str
    roles: frozenset[str] = frozenset()
    capabilities: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for field in (
            "principal_id",
            "session_id",
            "seed_id",
            "correlation_id",
        ):
            _require_text(getattr(self, field), field)
        if self.principal_kind not in _PRINCIPAL_KINDS:
            raise SessionIdentityError("principal_kind must be human, agent, service, or tool")
        issued = _as_utc(self.issued_at, "issued_at")
        expires = _as_utc(self.expires_at, "expires_at")
        if expires <= issued:
            raise SessionIdentityError("expires_at must be later than issued_at")
        if any(not isinstance(value, str) or not value.strip() for value in self.roles):
            raise SessionIdentityError("roles must contain non-empty strings")
        if any(not isinstance(value, str) or not value.strip() for value in self.capabilities):
            raise SessionIdentityError("capabilities must contain non-empty strings")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "expires_at", expires)
        object.__setattr__(self, "roles", frozenset(value.strip() for value in self.roles))
        object.__setattr__(
            self,
            "capabilities",
            frozenset(value.strip() for value in self.capabilities),
        )

    def is_active(self, now: datetime | None = None) -> bool:
        """Return whether the identity is currently usable, with an explicit testable clock."""
        current = _as_utc(now or datetime.now(UTC), "now")
        return self.issued_at <= current < self.expires_at

    def require_seed(self, seed_id: str) -> None:
        """Reject a request attempting to use this identity against another Seed."""
        requested = _require_text(seed_id, "seed_id")
        if requested != self.seed_id:
            raise SessionIdentityError(
                f"session {self.session_id!r} is scoped to Seed {self.seed_id!r}, not {requested!r}"
            )

    def permission_context(self) -> PermissionContext:
        """Adapt the authenticated identity to the existing deny-first policy evaluator."""
        return PermissionContext(
            actor_id=self.principal_id,
            roles=self.roles,
            capabilities=self.capabilities,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the stable contract form used by events, jobs, and audit records."""
        return {
            "principal_id": self.principal_id,
            "principal_kind": self.principal_kind,
            "session_id": self.session_id,
            "seed_id": self.seed_id,
            "issued_at": self.issued_at.isoformat().replace("+00:00", "Z"),
            "expires_at": self.expires_at.isoformat().replace("+00:00", "Z"),
            "correlation_id": self.correlation_id,
            "roles": sorted(self.roles),
            "capabilities": sorted(self.capabilities),
        }

    @classmethod
    def from_dict(cls, raw: object) -> SessionIdentity:
        """Parse an untrusted wire record without silently defaulting authority fields."""
        if not isinstance(raw, dict):
            raise SessionIdentityError("session identity must be an object")
        required = (
            "principal_id",
            "principal_kind",
            "session_id",
            "seed_id",
            "issued_at",
            "expires_at",
            "correlation_id",
        )
        missing = [field for field in required if field not in raw]
        if missing:
            raise SessionIdentityError(f"missing session identity fields: {', '.join(missing)}")

        def timestamp(field: str) -> datetime:
            value = _require_text(raw[field], field)
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise SessionIdentityError(f"{field} must be an ISO-8601 timestamp") from exc

        def string_set(field: str) -> frozenset[str]:
            value = raw.get(field, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise SessionIdentityError(f"{field} must be a list of strings")
            return frozenset(value)

        return cls(
            principal_id=_require_text(raw["principal_id"], "principal_id"),
            principal_kind=raw["principal_kind"],
            session_id=_require_text(raw["session_id"], "session_id"),
            seed_id=_require_text(raw["seed_id"], "seed_id"),
            issued_at=timestamp("issued_at"),
            expires_at=timestamp("expires_at"),
            correlation_id=_require_text(raw["correlation_id"], "correlation_id"),
            roles=string_set("roles"),
            capabilities=string_set("capabilities"),
        )
