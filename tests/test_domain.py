"""Test twin for kernel/seedlab/domain.py -- the domain-module contract + registration seam.

Acceptance: a real module (Education) satisfies the DomainModule contract; register_module files it
under its own name; and the full pipeline (Engineering Form spec -> provisioned Seed -> resolved
domain module) hands back the LIVE module a Seed selected, with its capability reachable.

Refusal (grammar before worlds, honestly): a Seed that selected a module the registry does not hold
is refused, never fake-loaded -- an education-only registry can never resolve a game Seed's module.
"""

from __future__ import annotations

import pytest

from kernel.domains.education import EducationModule
from kernel.seedlab.domain import DomainModule, register_module
from kernel.seedlab.form import SeedSpec
from kernel.seedlab.kernel import BlueprintKernel, InMemorySeedStore
from kernel.seedlab.provision import DomainModuleError, DomainModuleRegistry, provision


def _kernel() -> BlueprintKernel:
    return BlueprintKernel(InMemorySeedStore(), clock=lambda: "2026-08-03T00:00:00+00:00")


def _education_registry() -> DomainModuleRegistry:
    registry = DomainModuleRegistry()
    register_module(registry, EducationModule())
    return registry


def _spec(product_type: str, modules: tuple[str, ...]) -> SeedSpec:
    return SeedSpec(
        schema=1,
        product_type=product_type,
        name="Grade 3 Science",
        owner="ms_frizzle",
        purpose="cells",
        domain_modules=modules,
        answers={},
    )


# --- acceptance --------------------------------------------------------------------------------


def test_the_education_module_satisfies_the_domain_contract() -> None:
    assert isinstance(EducationModule(), DomainModule)


def test_register_module_files_it_under_its_own_name() -> None:
    registry = _education_registry()
    assert "education" in registry
    assert registry.get("education").title == "Education"


def test_provisioning_loads_the_live_module_a_seed_selected() -> None:
    kernel = _kernel()
    registry = _education_registry()
    record, resolved = provision(kernel, _spec("education", ("education",)), registry)
    module = resolved["education"]
    assert isinstance(module, DomainModule)  # it satisfies the neutral contract
    assert isinstance(module, EducationModule)  # and is the concrete module the Seed selected
    # the resolved module is LIVE: its capability is reachable and mutable
    module.lessons.add("cells_intro", "Intro to Cells")
    assert [lesson.title for lesson in module.lessons.all()] == ["Intro to Cells"]
    assert record.identity.domain_modules == ("education",)


# --- refusal: grammar before worlds, honestly ---------------------------------------------------


def test_an_education_only_registry_never_resolves_a_game_seed() -> None:
    kernel = _kernel()
    registry = _education_registry()  # holds only "education"
    with pytest.raises(DomainModuleError, match="not registered"):
        provision(kernel, _spec("mmorpg", ("game",)), registry)
    assert kernel.list_seeds() == []  # nothing half-provisioned
