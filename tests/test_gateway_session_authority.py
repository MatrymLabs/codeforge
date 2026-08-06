"""The gateway's privileged engineering path uses the durable session authority."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import adapters.gateway as gateway
from adapters.gateway import _GateHandler
from kernel.session_identity import SessionIdentity
from kernel.session_registry import FileSessionRegistry, SessionRegistryError
from kernel.world.session import Session


def test_gateway_identity_is_durable_scoped_and_revoked(tmp_path) -> None:
    registry = FileSessionRegistry(tmp_path / "sessions")
    handler = object.__new__(_GateHandler)
    handler.server = SimpleNamespace(session_registry=registry)
    handler._gateway_identities = {}
    session = Session(player_id="hero", account="hero-account")

    identity, policy = handler._engineering_identity(
        session,
        seed_id="seedlab",
        capability="seed.create",
        correlation_prefix="test-seed-create",
    )

    assert identity.seed_id == "seedlab"
    assert identity.principal_id == "hero-account"
    assert policy.decide(
        identity.permission_context(), capability="seed.create", scope="seedlab"
    ).allowed
    assert registry.resume(identity.session_id) == identity

    handler._revoke_engineering_identities(session)
    with pytest.raises(SessionRegistryError, match="invalidated"):
        registry.require_active(identity)


def test_authenticated_account_session_is_durable_and_revoked(tmp_path) -> None:
    registry = FileSessionRegistry(tmp_path / "sessions")
    handler = object.__new__(_GateHandler)
    handler.server = SimpleNamespace(session_registry=registry)
    handler._gateway_identities = {}
    handler._authenticated_identity = None
    session = Session(player_id="hero", account="hero-account", rank="player")

    handler._establish_authenticated_identity(session)
    identity = handler._authenticated_identity

    assert identity.principal_id == "hero-account"
    assert identity.seed_id == gateway.SEED_NAME
    assert identity.roles == frozenset({"player"})
    assert registry.resume(identity.session_id) == identity

    handler._revoke_engineering_identities(session)
    with pytest.raises(SessionRegistryError, match="invalidated"):
        registry.require_active(identity)


def test_authenticated_account_session_renews_without_widening_authority(tmp_path) -> None:
    registry = FileSessionRegistry(tmp_path / "sessions")
    handler = object.__new__(_GateHandler)
    handler.server = SimpleNamespace(session_registry=registry)
    now = datetime.now(UTC)
    identity = SessionIdentity(
        principal_id="hero-account",
        principal_kind="human",
        session_id="gateway-session-renewal",
        seed_id=gateway.SEED_NAME,
        issued_at=now - timedelta(hours=11, minutes=30),
        expires_at=now + timedelta(minutes=30),
        correlation_id="gateway-login-renewal",
        roles=frozenset({"player"}),
        capabilities=frozenset({"game.command"}),
    )
    registry.issue(identity)
    handler._authenticated_identity = identity

    renewed = handler._refresh_authenticated_identity(
        Session(player_id="hero", account="hero-account", rank="player")
    )

    assert renewed is not None
    assert renewed.session_id == identity.session_id
    assert renewed.seed_id == identity.seed_id
    assert renewed.capabilities == identity.capabilities
    assert renewed.expires_at > identity.expires_at
