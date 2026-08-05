"""CARD: platform -- the shared CodeForge startup contract.

This is an orchestration seam, not a second Engine. It initializes the existing
configuration, persistence, identity, Hardware Store, R&D audit, Seed Runtime,
and Creator Workshop in one ordered operation before a driver is imported.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from kernel.seed_selection import SeedSelection


class PlatformStartupError(RuntimeError):
    """The unified startup sequence could not initialize an authoritative service."""


@dataclass(frozen=True)
class ComponentStatus:
    """A truthful status for one startup component."""

    name: str
    state: str
    detail: str


@dataclass(frozen=True)
class PlatformStartup:
    """The result of one CodeForge product startup sequence."""

    selection: SeedSelection
    components: tuple[ComponentStatus, ...]

    def status(self, name: str) -> ComponentStatus:
        """Return one component status by canonical name."""
        for component in self.components:
            if component.name == name:
                return component
        raise KeyError(name)

    def to_dict(self) -> dict[str, object]:
        """Serialize the startup contract for diagnostics and Console consumers."""
        return {
            "seed": self.selection.seed_id,
            "selection_source": self.selection.source,
            "components": [
                {
                    "name": component.name,
                    "state": component.state,
                    "detail": component.detail,
                }
                for component in self.components
            ],
        }


def validate_startup_schema(engine=None) -> None:
    """Validate persistence before any startup path opens or creates database tables.

    A fresh database is allowed through the read-only guard and is then initialized by the normal
    persistence seam. An existing database behind the models fails before ``create_all`` can hide
    the missing migration.
    """
    from kernel.world.schema_guard import SchemaError, require_current_schema

    try:
        require_current_schema(engine)
    except SchemaError as exc:
        raise PlatformStartupError(f"persistence schema validation failed: {exc}") from exc


def bootstrap_platform(*, seed: str, selection_source: str) -> PlatformStartup:
    """Initialize existing CodeForge services in the canonical startup order.

    The caller resolves and validates the Seed before invoking this function. The
    Engine remains authoritative; this function only coordinates imports and the
    existing initialization seams.
    """
    from kernel.seed_selection import SeedSelection
    from kernel.shelf.config import Settings

    components: list[ComponentStatus] = []
    try:
        settings = Settings.load()
    except Exception as exc:
        raise PlatformStartupError(f"configuration initialization failed: {exc}") from exc
    components.append(
        ComponentStatus("configuration", "initialized", f"validated port {settings.port}")
    )

    try:
        validate_startup_schema()
        from kernel.world import accounts as _accounts
        from kernel.world.db import open_archive_session

        with open_archive_session():
            pass
        del _accounts
    except Exception as exc:
        raise PlatformStartupError(f"identity/persistence initialization failed: {exc}") from exc
    components.extend(
        (
            ComponentStatus("identity", "initialized", "account authentication seam loaded"),
            ComponentStatus("persistence", "initialized", "archive schema validated and opened"),
        )
    )

    try:
        from kernel.hardware import load_catalog

        catalog = load_catalog()
    except Exception as exc:
        raise PlatformStartupError(f"Hardware Store initialization failed: {exc}") from exc
    components.append(
        ComponentStatus(
            "hardware-store", "initialized", f"validated {len(catalog)} catalog entries"
        )
    )

    try:
        from kernel.seedlab.audit import audit_seedlab_modules

        audit = audit_seedlab_modules()
    except Exception as exc:
        raise PlatformStartupError(f"R&D initialization failed: {exc}") from exc
    components.append(
        ComponentStatus("rnd", "isolated", f"audited {len(audit.entries)} SeedLab modules")
    )

    if seed == "aethryn":
        try:
            from kernel.seedlab.kernel import SeedKernel
            from kernel.seedlab.reference_seed import ensure_reference_seed
            from kernel.seedlab.registry import seed_store
            from kernel.seedlab.runtime_bridge import bind_reference_seed
            from kernel.seedlab.workspace_contract import build_workspace_contract

            seedlab_home = Path(os.environ.get("SEEDLAB_HOME", ".seedlab"))
            seed_kernel = SeedKernel(seed_store(settings.seed_registry_backend, seedlab_home))
            record = ensure_reference_seed(seed_kernel, detail="CodeForge product startup")
            binding = bind_reference_seed(seed_kernel)
            contract = build_workspace_contract(seed, root=seedlab_home)
        except Exception as exc:
            raise PlatformStartupError(
                f"Seed registry/workspace initialization failed: {exc}"
            ) from exc
        components.extend(
            (
                ComponentStatus(
                    "seed-registry",
                    "initialized",
                    f"{settings.seed_registry_backend}: bound {record.identity.seed_id} to "
                    f"{binding.package}",
                ),
                ComponentStatus(
                    "workspace",
                    "initialized",
                    f"{contract.contract_version} available for {record.identity.name}",
                ),
            )
        )

    try:
        from kernel.world import creator_workshop
        from kernel.world import seed as seed_runtime
        from kernel.world.world import WORLD

        if seed != seed_runtime.SEED_NAME:
            raise PlatformStartupError(
                f"Seed Runtime selected {seed_runtime.SEED_NAME!r}, expected {seed!r}; "
                "the process imported the world before product startup"
            )
        workshop_rooms = len(creator_workshop.WORKSHOP_ROOMS)
        world_rooms = len(WORLD)
    except Exception as exc:
        raise PlatformStartupError(f"Engine/Seed Runtime initialization failed: {exc}") from exc
    components.extend(
        (
            ComponentStatus("engine", "initialized", f"loaded {world_rooms} runtime rooms"),
            ComponentStatus("seed-runtime", "initialized", f"active Seed: {seed}"),
            ComponentStatus(
                "creator-workshop",
                "initialized",
                f"installed {workshop_rooms} protected workshop rooms",
            ),
            ComponentStatus("creator-console", "available", "external operations API is available"),
        )
    )
    return PlatformStartup(
        selection=SeedSelection(seed_id=seed, source=selection_source),
        components=tuple(components),
    )


def current_platform_status() -> PlatformStartup:
    """Project the already-loaded runtime without starting or mutating services."""
    validate_startup_schema()
    from kernel.hardware import load_catalog
    from kernel.seedlab.audit import audit_seedlab_modules
    from kernel.world import creator_workshop
    from kernel.world.seed import SEED_NAME
    from kernel.world.world import WORLD

    return PlatformStartup(
        selection=SeedSelection(seed_id=SEED_NAME, source="runtime"),
        components=(
            ComponentStatus("configuration", "available", "runtime configuration is loaded"),
            ComponentStatus("identity", "available", "account authentication seam is loaded"),
            ComponentStatus("persistence", "available", "archive persistence is available"),
            ComponentStatus(
                "hardware-store", "available", f"validated {len(load_catalog())} catalog entries"
            ),
            ComponentStatus(
                "rnd", "isolated", f"audited {len(audit_seedlab_modules().entries)} SeedLab modules"
            ),
            ComponentStatus("engine", "initialized", f"loaded {len(WORLD)} runtime rooms"),
            ComponentStatus("seed-runtime", "initialized", f"active Seed: {SEED_NAME}"),
            ComponentStatus(
                "creator-workshop",
                "initialized",
                f"installed {len(creator_workshop.WORKSHOP_ROOMS)} protected workshop rooms",
            ),
            ComponentStatus("creator-console", "available", "external operations API is available"),
        ),
    )
