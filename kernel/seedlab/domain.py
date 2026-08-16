"""CARD: domain -- the contract a domain module satisfies, and a helper to register one by name.

The Seed Kernel is domain-neutral: it knows a Seed SELECTS domain modules (by name, on its identity)
but nothing about what any module does. A domain module is the optional, per-Seed unit that carries
domain-specific capability (an education module's lessons, a game module's combat). This file is
the neutral SEAM: it declares the shape every real module must satisfy, without importing a single
one. Grammar before worlds: the platform depends on this contract, never on a concrete domain module
(the modules live in kernel/domains/ and register themselves at composition time).

  * `DomainModule` -- the structural contract: a stable `name` (lowercase key a BlueprintSpec
selects,
    matching `SeedIdentity.domain_modules`), a display `title`, and the `capabilities` it honestly
    provides.
  * `register_module(registry, module)` -- register a module under its own `name`, so a Seed that
    selected that name resolves to this module (kernel/seedlab/provision.py does the resolving).

Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kernel.seedlab.provision import DomainModuleRegistry


@runtime_checkable
class DomainModule(Protocol):
    """What every domain module looks like from the platform's side. Structural (a plain object with
    these attributes satisfies it); the platform never imports a concrete module, it only resolves
    one out of a registry the composition root filled."""

    name: str  # the lowercase key a BlueprintSpec selects (matches SeedIdentity.domain_modules)
    title: str  # human-facing display name
    capabilities: tuple[str, ...]  # what this module honestly provides


def register_module(registry: DomainModuleRegistry, module: DomainModule) -> None:
    """Register a domain module under its own `name` (the key a BlueprintSpec selects). A duplicate
    name
        fails loud in the registry, so two modules can never both claim one name."""
    registry.register(module.name, module)
