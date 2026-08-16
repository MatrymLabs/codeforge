"""Test twin for kernel/seedlab/provision.py -- BlueprintSpec -> live Seed + domain-module
resolution.

Acceptance: a validated BlueprintSpec becomes a real Seed whose product type + selected domain
modules
are recorded on its identity and survive restart; registered modules resolve to their loaders; the
full `provision` pipeline creates the Seed and resolves its modules together.

Refusal (fail loud, never fake a load): a selected module that is not registered is refused (and
`provision` refuses BEFORE creating a half-provisioned Seed); duplicate/blank registration is
refused; an unknown module get is refused. Grammar before worlds: an education Seed can never
resolve to the game module -- it resolves only names registered under its own selection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.form import BlueprintSpec
from kernel.seedlab.kernel import FileSeedStore, InMemorySeedStore, SeedKernel
from kernel.seedlab.provision import (
    DomainModuleError,
    DomainModuleRegistry,
    provision,
    resolve_modules,
    seed_from_spec,
)

_CLOCK = iter(f"2026-08-03T00:00:{n:02d}+00:00" for n in range(60))


def _kernel(store=None) -> SeedKernel:
    return SeedKernel(store or InMemorySeedStore(), clock=lambda: next(_CLOCK))


def _spec(
    product_type: str, modules: tuple[str, ...], name: str = "Grade 3 Science"
) -> BlueprintSpec:
    return BlueprintSpec(
        schema=1,
        product_type=product_type,
        name=name,
        owner="ms_frizzle",
        purpose="cells",
        domain_modules=modules,
        answers={"name": name, "owner": "ms_frizzle", "purpose": "cells"},
    )


# --- acceptance --------------------------------------------------------------------------------


def test_seed_from_spec_records_product_type_and_modules() -> None:
    kernel = _kernel()
    record = seed_from_spec(kernel, _spec("education", ("education",)))
    assert record.identity.product_type == "education"
    assert record.identity.domain_modules == ("education",)
    assert record.identity.name == "Grade 3 Science" and record.identity.owner == "ms_frizzle"


def test_a_spec_seed_survives_restart_with_its_modules(tmp_path: Path) -> None:
    kernel = SeedKernel(FileSeedStore(tmp_path / "seeds"), clock=lambda: next(_CLOCK))
    seed_from_spec(kernel, _spec("mmorpg", ("game",), name="Aethryn"))
    sid = kernel.list_seeds()[0].identity.seed_id
    # A fresh kernel over the same store recovers the product type + modules (persisted facts).
    recovered = SeedKernel(FileSeedStore(tmp_path / "seeds")).get(sid)
    assert recovered.identity.product_type == "mmorpg"
    assert recovered.identity.domain_modules == ("game",)


def test_resolve_modules_returns_the_registered_loaders() -> None:
    registry = DomainModuleRegistry()
    registry.register("education", "education-loader")
    resolved = resolve_modules(("education",), registry)
    assert resolved == {"education": "education-loader"}


def test_provision_creates_the_seed_and_resolves_its_modules() -> None:
    kernel = _kernel()
    registry = DomainModuleRegistry()
    registry.register("education", object())
    record, resolved = provision(kernel, _spec("education", ("education",)), registry)
    assert record.identity.product_type == "education"
    assert set(resolved) == {"education"}
    assert kernel.get(record.identity.seed_id).identity.domain_modules == ("education",)


def test_registry_lists_and_contains() -> None:
    registry = DomainModuleRegistry()
    registry.register("training", 1)
    registry.register("education", 2)
    assert registry.names() == ["education", "training"]
    assert "training" in registry and "game" not in registry


# --- refusal: fail loud, never fake a load ------------------------------------------------------


def test_an_education_seed_never_resolves_to_the_game_module() -> None:
    """Grammar before worlds: only `game` is registered, but an education spec selects `education`;
    resolving it fails loud rather than silently binding the classroom to combat."""
    registry = DomainModuleRegistry()
    registry.register("game", "combat-loader")
    with pytest.raises(DomainModuleError, match="not registered"):
        resolve_modules(("education",), registry)


def test_provision_refuses_before_creating_when_a_module_is_missing() -> None:
    kernel = _kernel()
    registry = DomainModuleRegistry()  # empty: nothing registered
    with pytest.raises(DomainModuleError, match="not registered"):
        provision(kernel, _spec("mmorpg", ("game",)), registry)
    assert kernel.list_seeds() == []  # no half-provisioned Seed was created


def test_a_duplicate_registration_is_refused() -> None:
    registry = DomainModuleRegistry()
    registry.register("game", 1)
    with pytest.raises(DomainModuleError, match="already registered"):
        registry.register("game", 2)


def test_a_blank_module_name_is_refused() -> None:
    with pytest.raises(DomainModuleError, match="non-empty"):
        DomainModuleRegistry().register("", object())


def test_get_of_an_unregistered_module_is_refused() -> None:
    with pytest.raises(DomainModuleError, match="not registered"):
        DomainModuleRegistry().get("nope")
