from __future__ import annotations

import pytest

from kernel.permission_policy import (
    PermissionContext,
    PermissionDenied,
    PermissionPolicy,
    PermissionRule,
)


def test_role_and_capability_are_required_before_allow():
    policy = PermissionPolicy((PermissionRule("build", scope="seed-a"),))
    context = PermissionContext("alice", frozenset({"creator"}), frozenset({"build"}))
    policy.require(context, capability="build", scope="seed-a", required_role="creator")
    with pytest.raises(PermissionDenied, match="missing capability"):
        policy.require(PermissionContext("alice", frozenset({"creator"})), capability="build")


def test_explicit_deny_wins_and_is_audited():
    policy = PermissionPolicy(
        (
            PermissionRule("deploy", actor_id="alice", effect="allow"),
            PermissionRule("deploy", actor_id="alice", effect="deny"),
        )
    )
    decision = policy.decide(
        PermissionContext("alice", capabilities=frozenset({"deploy"})),
        capability="deploy",
    )
    assert not decision.allowed
    assert "explicit denial" in decision.reason
    assert policy.audit()[-1] == decision


def test_unknown_scope_is_denied_by_default():
    policy = PermissionPolicy((PermissionRule("build", scope="seed-a"),))
    context = PermissionContext("alice", capabilities=frozenset({"build"}))
    with pytest.raises(PermissionDenied, match="no grant"):
        policy.require(context, capability="build", scope="seed-b")


def test_explicit_revocation_wins_and_is_visible_in_audit():
    policy = PermissionPolicy((PermissionRule("build", scope="seed-a"),))
    context = PermissionContext("alice", capabilities=frozenset({"build"}))
    policy.revoke("build", scope="seed-a", actor_id="alice")

    decision = policy.decide(context, capability="build", scope="seed-a")
    assert not decision.allowed
    assert "revocation" in decision.reason
    with pytest.raises(PermissionDenied, match="revocation"):
        policy.require(context, capability="build", scope="seed-a")
