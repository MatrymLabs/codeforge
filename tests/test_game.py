"""Test twin for kernel/domains/game.py -- the game domain module (the symmetric proof).

Acceptance: the Game module satisfies the DomainModule contract and every capability it advertises
binds to a REAL kernel/world subsystem (grounded, not decorative); a game SeedSpec provisions and
resolves to the live GameModule. The tick's composition root (forge.domain_registry) offers both the
game and education modules, yet a Seed loads ONLY what it selected.

Refusal (fail loud): an unknown capability is refused; a game-only registry can never resolve a
classroom's `education` module. Grammar before worlds from the game side: a game Seed loads combat,
a classroom (which selected `education`) never resolves `game` even when both modules are available.
"""

from __future__ import annotations

from types import ModuleType

import pytest

from kernel.domains.game import GameError, GameModule, register_game_module
from kernel.seedlab.domain import DomainModule
from kernel.seedlab.form import SeedSpec
from kernel.seedlab.kernel import BlueprintKernel, InMemorySeedStore
from kernel.seedlab.provision import DomainModuleError, DomainModuleRegistry, provision


def _kernel() -> BlueprintKernel:
    return BlueprintKernel(InMemorySeedStore(), clock=lambda: "2026-08-03T00:00:00+00:00")


def _spec(product_type: str, modules: tuple[str, ...], name: str = "Aethryn") -> SeedSpec:
    return SeedSpec(
        schema=1,
        product_type=product_type,
        name=name,
        owner="josh",
        purpose="a world",
        domain_modules=modules,
        answers={},
    )


# --- acceptance --------------------------------------------------------------------------------


def test_the_game_module_satisfies_the_domain_contract() -> None:
    module = GameModule()
    assert isinstance(module, DomainModule)
    assert module.name == "game" and module.title == "Aethryn"
    assert "combat" in module.capabilities


def test_every_capability_binds_to_a_real_world_subsystem() -> None:
    """Grounded, not decorative: each advertised capability imports a real kernel/world module."""
    module = GameModule()
    for capability in module.capabilities:
        subsystem = module.subsystem(capability)
        assert isinstance(subsystem, ModuleType)
        assert subsystem.__name__.startswith("kernel.world.")


def test_provisioning_loads_the_live_game_module() -> None:
    kernel = _kernel()
    registry = DomainModuleRegistry()
    register_game_module(registry)
    record, resolved = provision(kernel, _spec("mmorpg", ("game",)), registry)
    module = resolved["game"]
    assert isinstance(module, GameModule)
    assert module.subsystem("combat").__name__ == "kernel.world.combat"
    assert record.identity.domain_modules == ("game",)


def test_the_tick_composition_root_offers_both_modules() -> None:
    from forge import domain_registry

    registry = domain_registry()
    assert "game" in registry and "education" in registry


def test_a_classroom_loads_only_education_even_when_game_is_available() -> None:
    """The isolation-by-selection proof: both modules sit in the tick's registry, but an education
    Seed resolves ONLY `education` -- it never loads `game`/combat."""
    from forge import domain_registry

    kernel = _kernel()
    _, resolved = provision(
        kernel, _spec("education", ("education",), name="Grade 3"), domain_registry()
    )
    assert set(resolved) == {"education"}
    assert "game" not in resolved


def test_a_game_seed_loads_only_game() -> None:
    from forge import domain_registry

    kernel = _kernel()
    _, resolved = provision(kernel, _spec("mmorpg", ("game",)), domain_registry())
    assert set(resolved) == {"game"}


# --- refusal: fail loud ------------------------------------------------------------------------


def test_an_unknown_capability_is_refused() -> None:
    with pytest.raises(GameError, match="no capability"):
        GameModule().subsystem("teleportation")


def test_a_game_only_registry_never_resolves_a_classroom() -> None:
    kernel = _kernel()
    registry = DomainModuleRegistry()
    register_game_module(registry)  # holds only "game"
    with pytest.raises(DomainModuleError, match="not registered"):
        provision(kernel, _spec("education", ("education",)), registry)
    assert kernel.list_seeds() == []  # nothing half-provisioned
