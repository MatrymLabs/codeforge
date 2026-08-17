"""CARD: provision -- turn a validated BlueprintSpec into a live Seed and resolve its domain


The Engineering Form (kernel/seedlab/form.py) answers "what should this Seed be?" and emits a
BlueprintSpec. The Seed Kernel (kernel/seedlab/kernel.py) owns a Seed's identity + lifecycle. This

is the seam between them: it creates a real Seed FROM a spec (recording the product type + selected
domain modules on the Seed's identity, so a Seed remembers what it is across restart), and resolves
those selected modules against a `DomainModuleRegistry`.

Two honest halves:
  * `seed_from_spec(kernel, spec)` -- always works: it records the spec's module SELECTION on the
    Seed. It does not require the modules to exist yet (intent is recorded even before code does).
  * `resolve_modules` / `provision` -- LOADING: resolve each selected module against a registry,
    failing loud if any selected module is not registered. We never fake-load a module that does not
    exist, and grammar before worlds holds by construction: an education Seed resolves only modules
    registered under its own names and can never resolve to the game module.

Domain-neutral: this knows module NAMES, never their content; no kernel/world/ import. Status:
PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from kernel.seedlab.form import BlueprintSpec
from kernel.seedlab.kernel import BlueprintKernel, BlueprintKernelError, BlueprintRecord


class DomainModuleError(BlueprintKernelError):
    """A Seed selected a domain module that is not registered (or a module was double-registered).
    Fails loud: the platform never pretends to load a module that does not exist."""


@dataclass
class DomainModuleRegistry:
    """Maps a domain module NAME (as a BlueprintSpec selects it) to its loader -- an opaque handle

    caller supplies (a module, a factory, a config object). The registry owns names, not behavior:
    it is the seam a future real module loader plugs into. Registration is explicit and unique."""

    _loaders: dict[str, Any] = field(default_factory=dict)

    def register(self, name: str, loader: Any) -> None:
        """Register a domain module's loader under
        ame`. A duplicate name fails loud (two loaders
                for one module is an ambiguity, never a silent overwrite)."""
        if not name or not name.strip():
            raise DomainModuleError("a domain module needs a non-empty name")
        if name in self._loaders:
            raise DomainModuleError(f"domain module {name!r} is already registered")
        self._loaders[name] = loader

    def get(self, name: str) -> Any:
        """The loader registered under
        ame`, or fail loud if none is."""
        if name not in self._loaders:
            known = ", ".join(sorted(self._loaders)) or "(none)"
            raise DomainModuleError(f"domain module {name!r} is not registered; known: {known}")
        return self._loaders[name]

    def names(self) -> list[str]:
        """Every registered module name, sorted (for a stable listing)."""
        return sorted(self._loaders)

    def __contains__(self, name: object) -> bool:
        return name in self._loaders


def seed_from_spec(kernel: BlueprintKernel, spec: BlueprintSpec) -> BlueprintRecord:
    """Create a live Seed FROM a validated BlueprintSpec, recording its product type and selected

    modules on the Seed's identity (they survive restart). Does not require the modules to be
    registered -- recording intent is separate from loading it."""
    return kernel.create_seed(
        spec.name,
        spec.owner,
        spec.purpose,
        product_type=spec.product_type,
        domain_modules=tuple(spec.domain_modules),
    )


def resolve_modules(modules: Iterable[str], registry: DomainModuleRegistry) -> dict[str, Any]:
    """Resolve selected module names to their registered loaders, failing loud if ANY is not
    registered (all-or-nothing: a partially loaded Seed is never returned). Grammar before worlds:
    a module resolves only if it was registered under that exact name."""
    selected = list(modules)
    missing = [m for m in selected if m not in registry]
    if missing:
        raise DomainModuleError(
            f"selected domain module(s) not registered: {', '.join(sorted(missing))}"
        )
    return {name: registry.get(name) for name in selected}


def provision(
    kernel: BlueprintKernel, spec: BlueprintSpec, registry: DomainModuleRegistry
) -> tuple[BlueprintRecord, dict[str, Any]]:
    """The full pipeline step: resolve the spec's domain modules against the registry FIRST (fail
    loud before creating a half-provisioned Seed), then create the Seed. Returns the new Seed record
    and the resolved {name: loader} map the caller loads. Use `seed_from_spec` instead when you want
    to record a Seed whose modules are not registered yet."""
    resolved = resolve_modules(spec.domain_modules, registry)
    record = seed_from_spec(kernel, spec)
    return record, resolved
