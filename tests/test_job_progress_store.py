"""Contract tests for the JobProgressStore port -- proof the boundary can be extracted cleanly.

One behavioral contract, run against BOTH adapters: the pure in-memory store (the contract test) and
the SQLAlchemy store over the quarantined tmp database (the integration test). Both must satisfy the
same port, so persistence can be swapped without touching the domain -- the whole point of the
assimilation pattern (docs/persistence_ports.md). A domain module (job_progress) no longer imports a
framework; the framework lives behind this port.
"""

from __future__ import annotations

import pytest

from parts.world.job_progress import (
    InMemoryJobProgressStore,
    JobProgress,
    JobProgressStore,
    load_job_progress,
    save_job_progress,
)
from parts.world.job_progress_sql import SqlJobProgressStore


def _sql_store():
    """The SQL adapter over the tmp DB. The character FK must exist before job rows save, so a bare
    named character is persisted first (save_character writes the CharacterRow the FK needs)."""
    from parts.world.characters import save_character
    from parts.world.session import Session

    hero = Session(player_id="rowan", named=True, account="acct")
    save_character(hero)  # creates the character row the job_progress FK needs
    return SqlJobProgressStore(), "rowan"


# --- the contract: every JobProgressStore must obey these ------------------------------


@pytest.fixture(params=["memory", "sql"])
def store_and_name(request):
    if request.param == "memory":
        return InMemoryJobProgressStore(), "hero"
    return _sql_store()


def test_an_unknown_character_loads_empty(store_and_name):
    store, _ = store_and_name
    assert store.load("nobody_here") == {}


def test_save_then_load_round_trips(store_and_name):
    store, name = store_and_name
    store.save(name, [JobProgress("smith", 5, 40, 3), JobProgress("scout", 2, 10, 0)])
    loaded = store.load(name)
    assert loaded["smith"] == JobProgress("smith", 5, 40, 3)
    assert loaded["scout"].job_level == 2


def test_saving_the_same_job_again_upserts_not_duplicates(store_and_name):
    store, name = store_and_name
    store.save(name, [JobProgress("smith", 1, 0, 0)])
    store.save(name, [JobProgress("smith", 9, 99, 5)])  # same job, higher standing
    loaded = store.load(name)
    assert loaded["smith"] == JobProgress("smith", 9, 99, 5)  # overwritten, not doubled


# --- conformance + the preserved module wrappers ---------------------------------------


def test_both_adapters_satisfy_the_port():
    assert isinstance(InMemoryJobProgressStore(), JobProgressStore)
    assert isinstance(SqlJobProgressStore(), JobProgressStore)


def test_the_module_wrappers_delegate_to_an_injected_store():
    # behaviour preserved: the domain-facing functions still work, now over any store
    store = InMemoryJobProgressStore()
    save_job_progress("mira", [JobProgress("mage", 3, 12, 1)], store=store)
    assert load_job_progress("mira", store=store)["mage"].job_level == 3
    assert load_job_progress("stranger", store=store) == {}
