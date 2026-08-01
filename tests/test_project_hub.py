"""Test twin for parts/seedlab/project_hub.py -- the Seed's functional Project Hub.

Acceptance: the Hub loads a created Seed, renders identity/status/purpose + every facet (empty
reads "none yet", populated reads the values), exposes the directive's verbs (look/show status/
list <facet>/show risks/show history), and emits a versioned structured contract whose data matches
the text render (one source of truth).

Refusal (fail loud / honest): a mismatched ProjectState is rejected; an unknown facet is reported,
not faked; the contract for an unknown Seed raises via the Kernel.
"""

from __future__ import annotations

import pytest

from parts.seedlab.kernel import InMemorySeedStore, SeedKernel, SeedNotFound
from parts.seedlab.project_hub import (
    CONTRACT_VERSION,
    ProjectHub,
    ProjectHubError,
    ProjectState,
)

_CLOCK = iter(f"2026-08-01T00:00:{n:02d}+00:00" for n in range(60))


def _hub_with_seed(owner: str = "josh") -> tuple[ProjectHub, str]:
    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: next(_CLOCK))
    record = kernel.create_seed("Task Ledger", owner, "a tiny CLI tracker", seed_id="seed-01")
    return ProjectHub(kernel), record.identity.seed_id


# --- acceptance --------------------------------------------------------------------------------
def test_look_shows_identity_status_and_empty_facets_honestly() -> None:
    hub, sid = _hub_with_seed()
    out = hub.render(sid)
    assert "Project Hub :: Task Ledger" in out and "CREATED" in out
    assert "a tiny CLI tracker" in out
    assert "Sources (0): none yet" in out  # empty facet reads as not-built, never faked
    assert "Recent activity:" in out


def test_populated_facets_render_their_values() -> None:
    hub, sid = _hub_with_seed()
    state = ProjectState(sid, sources=("local:./repo",), risks=("no auth yet",))
    out = hub.render(sid, state)
    assert "Sources (1): local:./repo" in out
    assert "Risks (1): no auth yet" in out


def test_contract_is_versioned_and_matches_the_render() -> None:
    hub, sid = _hub_with_seed()
    state = ProjectState(sid, models=("domain-v1",))
    contract = hub.contract(sid, state)
    assert contract["contract_version"] == CONTRACT_VERSION
    assert contract["seed"]["id"] == sid and contract["seed"]["status"] == "created"
    assert contract["project"]["models"] == ["domain-v1"]
    assert contract["project"]["sources"] == []  # empty facet is an empty list, present + honest
    assert contract["activity"][0]["action"] == "created"


def test_command_dispatch_covers_the_directives_verbs() -> None:
    hub, sid = _hub_with_seed()
    state = ProjectState(sid, sources=("local:./repo",))
    assert "Project Hub :: Task Ledger" in hub.command(sid, "look", state)
    assert "CREATED" in hub.command(sid, "show status")
    assert "local:./repo" in hub.command(sid, "list sources", state)
    assert "none yet" in hub.command(sid, "list targets", state)
    assert "created" in hub.command(sid, "show history")
    assert "none yet" in hub.command(sid, "show risks", state)


def test_status_reflects_lifecycle_changes() -> None:
    hub, sid = _hub_with_seed()
    hub.kernel.start(sid, "josh")
    assert "RUNNING" in hub.command(sid, "show status")
    assert hub.contract(sid)["seed"]["status"] == "running"


def test_unknown_verb_returns_help() -> None:
    hub, sid = _hub_with_seed()
    assert "Project Hub commands:" in hub.command(sid, "frobnicate the flux")


# --- refusal -----------------------------------------------------------------------------------
def test_mismatched_project_state_is_refused() -> None:
    hub, sid = _hub_with_seed()
    with pytest.raises(ProjectHubError, match="not the requested"):
        hub.render(sid, ProjectState("some-other-seed"))


def test_unknown_facet_is_reported_not_faked() -> None:
    hub, sid = _hub_with_seed()
    assert "unknown facet" in hub.command(sid, "list unicorns")


def test_contract_for_unknown_seed_raises() -> None:
    hub, _ = _hub_with_seed()
    with pytest.raises(SeedNotFound):
        hub.contract("no-such-seed")
