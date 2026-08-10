from datetime import UTC, datetime, timedelta

import pytest

from kernel.permission_policy import PermissionPolicy, PermissionRule
from kernel.session_identity import SessionIdentity, SessionIdentityError

BASE = datetime(2026, 8, 5, 18, 0, tzinfo=UTC)


def identity() -> SessionIdentity:
    return SessionIdentity(
        principal_id="human:josh",
        principal_kind="human",
        session_id="session-123",
        seed_id="seed-first-forge",
        issued_at=BASE,
        expires_at=BASE + timedelta(minutes=30),
        correlation_id="trace-456",
        roles=frozenset({"creator"}),
        capabilities=frozenset({"component.inspect", "build"}),
    )


def test_identity_round_trips_and_adapts_to_permission_context():
    original = identity()
    restored = SessionIdentity.from_dict(original.to_dict())

    assert restored == original
    assert restored.is_active(BASE + timedelta(minutes=1))
    context = restored.permission_context()
    assert context.actor_id == "human:josh"
    assert context.capabilities == frozenset({"component.inspect", "build"})


def test_identity_rejects_cross_seed_use():
    with pytest.raises(SessionIdentityError, match="scoped to Seed"):
        identity().require_seed("seed-aethryn")


def test_identity_expiry_is_enforced_by_the_caller_clock():
    assert not identity().is_active(BASE + timedelta(minutes=30))
    assert identity().is_active(BASE + timedelta(seconds=1))


def test_identity_rejects_missing_timezone_and_invalid_window():
    with pytest.raises(SessionIdentityError, match="timezone"):
        SessionIdentity(
            principal_id="human:josh",
            principal_kind="human",
            session_id="session-123",
            seed_id="seed-first-forge",
            issued_at=datetime(2026, 8, 5, 18),
            expires_at=BASE + timedelta(minutes=30),
            correlation_id="trace-456",
        )
    with pytest.raises(SessionIdentityError, match="later"):
        SessionIdentity(
            principal_id="human:josh",
            principal_kind="human",
            session_id="session-123",
            seed_id="seed-first-forge",
            issued_at=BASE,
            expires_at=BASE,
            correlation_id="trace-456",
        )


def test_identity_context_can_be_checked_by_the_existing_policy():
    policy = PermissionPolicy((PermissionRule("build", scope="seed-first-forge"),))
    decision = policy.decide(
        identity().permission_context(), capability="build", scope="seed-first-forge"
    )
    assert decision.allowed
