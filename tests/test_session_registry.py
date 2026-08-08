"""Restart, resume, and invalidation evidence for the platform session authority."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlSession

from kernel.platform_db import PlatformBase
from kernel.seedlab.audit_registry import FileAuditStore
from kernel.session_identity import SessionIdentity
from kernel.session_registry import FileSessionRegistry, SessionRegistryError, SqlSessionRegistry


def _identity(*, session_id: str = "session-1") -> SessionIdentity:
    issued = datetime(2026, 8, 5, tzinfo=UTC)
    return SessionIdentity(
        principal_id="agent:alice",
        principal_kind="agent",
        session_id=session_id,
        seed_id="seed-demo",
        issued_at=issued,
        expires_at=issued + timedelta(minutes=10),
        correlation_id="trace-session-1",
        roles=frozenset({"creator"}),
        capabilities=frozenset({"tool.test"}),
    )


def _registry(tmp_path: Path) -> FileSessionRegistry:
    return FileSessionRegistry(
        tmp_path / "sessions",
        audit=FileAuditStore(tmp_path / "audit.jsonl"),
        clock=lambda: "2026-08-05T00:00:00Z",
    )


def test_issue_is_idempotent_and_resume_survives_restart(tmp_path: Path) -> None:
    identity = _identity()
    first = _registry(tmp_path).issue(identity, actor="authority")
    recovered = _registry(tmp_path).resume(
        identity.session_id, now=datetime(2026, 8, 5, 0, 1, tzinfo=UTC)
    )

    assert recovered == identity
    assert _registry(tmp_path).issue(identity, actor="authority") == first
    assert len(_registry(tmp_path).audit.all_records()) == 1  # type: ignore[union-attr]


def test_invalidation_is_durable_and_blocks_presented_identity(tmp_path: Path) -> None:
    identity = _identity()
    registry = _registry(tmp_path)
    registry.issue(identity)
    invalidated = registry.invalidate(
        identity.session_id, actor="operator", reason="credential reset"
    )

    recovered = _registry(tmp_path)
    assert invalidated.state == "invalidated"
    with pytest.raises(SessionRegistryError, match="invalidated"):
        recovered.require_active(identity)
    assert [entry["action"] for entry in recovered.audit.all_records()] == [  # type: ignore[union-attr]
        "session.issued",
        "session.invalidated",
    ]


def test_registry_rejects_authority_substitution_and_expired_resume(tmp_path: Path) -> None:
    identity = _identity()
    registry = _registry(tmp_path)
    registry.issue(identity)
    with pytest.raises(SessionRegistryError, match="different authority"):
        registry.issue(SessionIdentity.from_dict({**identity.to_dict(), "seed_id": "other"}))
    with pytest.raises(SessionRegistryError, match="expired"):
        registry.resume(identity.session_id, now=datetime(2026, 8, 5, 0, 11, tzinfo=UTC))


def test_renewal_preserves_authority_and_is_durable(tmp_path: Path) -> None:
    identity = _identity()
    registry = _registry(tmp_path)
    registry.issue(identity)
    renewed = registry.renew(
        identity,
        ttl=timedelta(minutes=20),
        actor="gateway",
        now=datetime(2026, 8, 5, 0, 5, tzinfo=UTC),
    )

    assert renewed.session_id == identity.session_id
    assert renewed.principal_id == identity.principal_id
    assert renewed.seed_id == identity.seed_id
    assert renewed.capabilities == identity.capabilities
    assert renewed.expires_at == datetime(2026, 8, 5, 0, 25, tzinfo=UTC)
    assert (
        _registry(tmp_path).resume(identity.session_id, now=datetime(2026, 8, 5, 0, 6, tzinfo=UTC))
        == renewed
    )
    assert [entry["action"] for entry in registry.audit.all_records()] == [  # type: ignore[union-attr]
        "session.issued",
        "session.renewed",
    ]


def test_audit_distinguishes_principal_kind_and_seed(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.issue(_identity(), actor="authority")
    entry = registry.audit.all_records()[0]  # type: ignore[union-attr]
    assert entry["principal_kind"] == "agent"
    assert entry["seed_id"] == "seed-demo"


def _sql_registry(tmp_path: Path) -> SqlSessionRegistry:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    PlatformBase.metadata.create_all(engine)
    return SqlSessionRegistry(
        tmp_path / "unused-sessions",
        audit=FileAuditStore(tmp_path / "sql-audit.jsonl"),
        session_factory=lambda: SqlSession(engine),
    )


def test_sql_registry_is_idempotent_and_survives_restart(tmp_path: Path) -> None:
    identity = _identity()
    first_registry = _sql_registry(tmp_path)
    first = first_registry.issue(identity, actor="authority")

    restarted = _sql_registry(tmp_path)
    assert restarted.issue(identity, actor="authority") == first
    assert (
        restarted.resume(
            identity.session_id,
            now=datetime(2026, 8, 5, 0, 1, tzinfo=UTC),
        )
        == identity
    )
    assert len(restarted.audit.all_records()) == 1  # type: ignore[union-attr]


def test_sql_registry_preserves_authority_and_invalidation_across_restart(
    tmp_path: Path,
) -> None:
    identity = _identity()
    registry = _sql_registry(tmp_path)
    registry.issue(identity)

    with pytest.raises(SessionRegistryError, match="authority differs"):
        registry.require_active(
            SessionIdentity.from_dict({**identity.to_dict(), "seed_id": "other"})
        )

    invalidated = registry.invalidate(
        identity.session_id,
        actor="operator",
        reason="credential reset",
        now="2026-08-05T00:02:00Z",
    )
    assert invalidated.state == "invalidated"
    with pytest.raises(SessionRegistryError, match="invalidated"):
        _sql_registry(tmp_path).require_active(identity)
    assert [entry["action"] for entry in registry.audit.all_records()] == [  # type: ignore[union-attr]
        "session.issued",
        "session.invalidated",
    ]


def test_sql_registry_renewal_preserves_authority_and_is_durable(tmp_path: Path) -> None:
    identity = _identity()
    registry = _sql_registry(tmp_path)
    registry.issue(identity)
    renewed = registry.renew(
        identity,
        ttl=timedelta(minutes=20),
        actor="gateway",
        now=datetime(2026, 8, 5, 0, 5, tzinfo=UTC),
    )

    assert renewed.session_id == identity.session_id
    assert renewed.principal_id == identity.principal_id
    assert renewed.seed_id == identity.seed_id
    assert renewed.capabilities == identity.capabilities
    assert renewed.expires_at == datetime(2026, 8, 5, 0, 25, tzinfo=UTC)
    assert (
        _sql_registry(tmp_path).resume(
            identity.session_id,
            now=datetime(2026, 8, 5, 0, 6, tzinfo=UTC),
        )
        == renewed
    )
