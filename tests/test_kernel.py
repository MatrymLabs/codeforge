"""Test twin for kernel/seedlab/kernel.py -- Seed identity + lifecycle.

Acceptance: a Seed is created with a stable identity, starts/stops through legal moves, renders
an inspectable status, exposes a structured contract, and -- the load-bearing claim -- its identity
and state survive restart (a fresh Kernel over the same file store recovers it).

Refusal (fail loud, never mis-state a Seed): a non-owner cannot operate a Seed; unknown ids raise;
duplicate ids are refused; illegal lifecycle transitions are refused; a corrupt persisted record
raises rather than loading a lie.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kernel.seedlab.kernel import (
    ARCHIVED,
    CREATED,
    RUNNING,
    STOPPED,
    AuditEvent,
    FileSeedStore,
    InMemorySeedStore,
    SeedAuthError,
    SeedKernel,
    SeedKernelError,
    SeedLifecycleError,
    SeedNotFound,
    SeedRecord,
    SeedStore,
    render_status,
)

# A fixed clock + deterministic id so tests never depend on wall time or randomness.
_CLOCK = iter(f"2026-08-01T00:00:{n:02d}+00:00" for n in range(60))


def _kernel(store: SeedStore | None = None) -> SeedKernel:
    return SeedKernel(store or InMemorySeedStore(), clock=lambda: next(_CLOCK))


def _seed(kernel: SeedKernel, owner: str = "josh") -> SeedRecord:
    return kernel.create_seed("Task Ledger", owner, "a tiny CLI tracker", seed_id="seed-fixed-01")


# --- acceptance --------------------------------------------------------------------------------
def test_create_gives_a_stable_identity_and_created_status() -> None:
    record = _seed(_kernel())
    assert record.identity.seed_id == "seed-fixed-01" and record.identity.owner == "josh"
    assert record.status == CREATED
    assert record.audit and record.audit[-1].action == "created"


def test_a_store_is_a_seed_store() -> None:
    assert isinstance(InMemorySeedStore(), SeedStore)


def test_minted_ids_are_slugged_and_unique() -> None:
    k = _kernel()
    a = k.create_seed("My Cool Project!", "josh", "")
    b = k.create_seed("My Cool Project!", "josh", "")
    assert a.identity.seed_id.startswith("seed-my-cool-project-")
    assert a.identity.seed_id != b.identity.seed_id  # random suffix keeps them distinct


def test_start_then_stop_walks_the_lifecycle() -> None:
    k = _kernel()
    _seed(k)
    started = k.start("seed-fixed-01", "josh")
    assert started.status == RUNNING and started.started_at
    stopped = k.stop("seed-fixed-01", "josh")
    assert stopped.status == STOPPED and stopped.stopped_at
    assert [e.action for e in stopped.audit] == ["created", "started", "stopped"]


def test_list_and_status_render() -> None:
    k = _kernel()
    _seed(k)
    assert len(k.list_seeds()) == 1
    out = k.status("seed-fixed-01")
    assert "Task Ledger" in out and "CREATED" in out and "recent activity" in out


def test_structured_contract_roundtrips() -> None:
    record = _seed(_kernel())
    rebuilt = SeedRecord.from_dict(record.to_dict())
    assert rebuilt == record  # the client contract and persistence share one honest shape


def test_identity_survives_restart(tmp_path: Path) -> None:
    # The load-bearing Stage-1 claim: a fresh Kernel over the same file store recovers the Seed.
    store_a = FileSeedStore(tmp_path / "seeds")
    kernel_a = SeedKernel(store_a, clock=lambda: next(_CLOCK))
    _seed(kernel_a)
    kernel_a.start("seed-fixed-01", "josh")

    # Simulate a restart: a brand-new Kernel + store object over the SAME directory.
    kernel_b = SeedKernel(FileSeedStore(tmp_path / "seeds"))
    recovered = kernel_b.get("seed-fixed-01")
    assert recovered.identity.name == "Task Ledger" and recovered.status == RUNNING
    assert recovered.identity.created_at  # the original creation time persisted


def test_archive_is_terminal() -> None:
    k = _kernel()
    _seed(k)
    archived = k.archive("seed-fixed-01", "josh")
    assert archived.status == ARCHIVED


# --- refusal: fail loud ------------------------------------------------------------------------
def test_a_non_owner_cannot_start(tmp_path: Path) -> None:
    k = _kernel()
    _seed(k, owner="josh")
    with pytest.raises(SeedAuthError, match="not the owner"):
        k.start("seed-fixed-01", "mallory")


def test_a_non_owner_cannot_stop_or_archive() -> None:
    k = _kernel()
    _seed(k)
    k.start("seed-fixed-01", "josh")
    with pytest.raises(SeedAuthError):
        k.stop("seed-fixed-01", "intruder")


def test_unknown_seed_raises_not_found() -> None:
    with pytest.raises(SeedNotFound, match="no Seed"):
        _kernel().get("nope")


def test_duplicate_id_is_refused() -> None:
    k = _kernel()
    _seed(k)
    with pytest.raises(SeedKernelError, match="already exists"):
        _seed(k)


def test_starting_an_archived_seed_is_refused() -> None:
    k = _kernel()
    _seed(k)
    k.archive("seed-fixed-01", "josh")
    with pytest.raises(SeedLifecycleError, match="cannot start"):
        k.start("seed-fixed-01", "josh")


def test_stopping_a_created_seed_is_refused() -> None:
    k = _kernel()
    _seed(k)  # created, never started
    with pytest.raises(SeedLifecycleError, match="cannot stop"):
        k.stop("seed-fixed-01", "josh")


def test_an_empty_owner_is_refused() -> None:
    with pytest.raises(SeedKernelError, match="owner"):
        _kernel().create_seed("X", "", "p", seed_id="x")


def test_a_corrupt_record_raises_not_loads_a_lie(tmp_path: Path) -> None:
    store = FileSeedStore(tmp_path / "seeds")
    (store.root / "seed-bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SeedKernelError, match="corrupt"):
        store.load("seed-bad")


def test_a_malformed_record_shape_is_refused() -> None:
    with pytest.raises(SeedKernelError, match="malformed"):
        SeedRecord.from_dict({"status": CREATED})  # no identity


def test_render_status_is_pure_text() -> None:
    record = SeedRecord(
        identity=_seed(_kernel()).identity,
        audit=(AuditEvent("2026-08-01T00:00:00+00:00", "josh", "created", "hi"),),
    )
    assert isinstance(render_status(record), str)


def test_reinstate_writes_a_prior_record_and_audits(tmp_path: Path) -> None:
    """The server-authoritative restore primitive: an owner reinstates a prior record as current,
    and the write is audited (`reinstated`) so a rollback is itself traceable."""
    kernel = _kernel(FileSeedStore(tmp_path / "seeds"))
    snapshot = _seed(kernel, owner="josh")  # a CREATED record to reinstate later
    kernel.start(snapshot.identity.seed_id, "josh")  # move current state forward
    reinstated = kernel.reinstate(snapshot, "josh", detail="rollback")
    assert reinstated.status == CREATED
    assert reinstated.audit[-1].action == "reinstated"
    assert kernel.get(snapshot.identity.seed_id).status == CREATED


def test_a_non_owner_cannot_reinstate() -> None:
    kernel = _kernel()
    record = _seed(kernel, owner="josh")
    with pytest.raises(SeedAuthError):
        kernel.reinstate(record, "mallory")


def test_reinstate_cannot_change_a_seeds_owner() -> None:
    """A restore may recover state, never quietly transfer a Seed: reinstating a record whose owner
    differs from the current owner is refused even for the current owner."""
    kernel = _kernel()
    record = _seed(kernel, owner="josh")
    forged = SeedRecord(identity=replace(record.identity, owner="mallory"))
    with pytest.raises(SeedAuthError, match="owner"):
        kernel.reinstate(forged, "josh")


def test_create_seed_carries_product_type_and_modules() -> None:
    k = _kernel()
    record = k.create_seed(
        "Classroom",
        "josh",
        "learn",
        seed_id="seed-pt",
        product_type="education",
        domain_modules=("education",),
    )
    assert record.identity.product_type == "education"
    assert record.identity.domain_modules == ("education",)


def test_a_seed_minted_directly_has_empty_product_fields() -> None:
    # A Seed created without a Form (the game reference Seed, a bare CLI create) is still valid.
    record = _seed(_kernel())
    assert record.identity.product_type == "" and record.identity.domain_modules == ()


def test_an_old_record_without_the_new_fields_still_loads() -> None:
    # Backward compatibility: a record persisted before product_type/domain_modules existed loads
    # with the defaults, and a JSON list for domain_modules is coerced to a tuple.
    legacy = {
        "identity": {
            "seed_id": "seed-legacy",
            "name": "Old",
            "owner": "josh",
            "purpose": "p",
            "version": "0.1.0",
            "created_at": "2026-08-01T00:00:00+00:00",
        },
        "status": CREATED,
    }
    record = SeedRecord.from_dict(legacy)
    assert record.identity.product_type == "" and record.identity.domain_modules == ()
    # And a record whose domain_modules persisted as a JSON list rebuilds as a tuple.
    modern = SeedRecord.from_dict(
        {**legacy, "identity": {**legacy["identity"], "domain_modules": ["education", "extra"]}}
    )
    assert modern.identity.domain_modules == ("education", "extra")
