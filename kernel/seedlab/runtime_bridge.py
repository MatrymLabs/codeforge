"""Bridge SeedLab identities to the authoritative CodeForge Seed packages.

SeedLab owns durable engineering identity and lifecycle records. The world loader owns
runtime content. This module is the narrow, manifest-only bridge between them: it verifies
that a Seed record has a matching package under the canonical content root before a caller
starts that Seed. It never imports Seed code or executes package contents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kernel.seed_selection import discover_seed_ids
from kernel.seedlab.kernel import SeedKernel, SeedNotFound, SeedRecord


class RuntimeSeedError(ValueError):
    """A Seed identity cannot be safely bound to a runtime package."""


@dataclass(frozen=True)
class RuntimeSeedBinding:
    """The verified relationship between a SeedLab record and its runtime package."""

    record: SeedRecord
    package: Path
    manifest: dict[str, Any]

    @property
    def seed_id(self) -> str:
        return self.record.identity.seed_id


def default_seed_root() -> Path:
    """Resolve the one content root used by the world loader."""
    configured = os.environ.get("CODEFORGE_SEEDS_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[2] / "content" / "seeds"


def _manifest_for(seed_id: str, seed_root: Path) -> tuple[Path, dict[str, Any]]:
    """Load and validate the one runtime manifest for a discovered Seed package."""
    if seed_id not in discover_seed_ids(seed_root):
        raise RuntimeSeedError(f"Seed {seed_id!r} has no bootable package under {seed_root}")
    package = seed_root / seed_id
    manifest_path = package / "world.yaml"
    if not manifest_path.is_file():
        raise RuntimeSeedError(f"Seed {seed_id!r} is missing its world manifest")
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise RuntimeSeedError(f"cannot read Seed manifest {manifest_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeSeedError(f"Seed manifest {manifest_path} must contain a mapping")
    declared = raw.get("world_id")
    if declared != seed_id:
        raise RuntimeSeedError(
            f"Seed manifest {manifest_path} declares {declared!r}, expected {seed_id!r}"
        )
    return package, raw


def bind_runtime_seed(
    kernel: SeedKernel,
    seed_id: str,
    *,
    root: Path | None = None,
) -> RuntimeSeedBinding:
    """Verify one SeedLab record against a manifest-backed runtime package.

    The package must be discoverable by the shared Seed selection contract, carry a
    ``world.yaml`` manifest, and declare the same stable id. A missing or mismatched
    package fails loudly instead of silently selecting another Seed.
    """
    try:
        record = kernel.get(seed_id)
    except SeedNotFound as exc:
        raise RuntimeSeedError(f"SeedLab record {seed_id!r} does not exist") from exc

    seed_root = Path(root) if root is not None else default_seed_root()
    package, raw = _manifest_for(seed_id, seed_root)
    return RuntimeSeedBinding(record=record, package=package, manifest=raw)


def ensure_runtime_seed(
    kernel: SeedKernel,
    seed_id: str,
    *,
    root: Path | None = None,
    owner: str = "matrym",
) -> SeedRecord:
    """Register a discovered runtime package in the existing SeedLab registry if needed.

    The package manifest supplies display metadata; the Seed Kernel remains the identity and
    lifecycle authority. Existing records are never overwritten, and the package is validated
    before a new registry record is created.
    """
    seed_root = Path(root) if root is not None else default_seed_root()
    _package, manifest = _manifest_for(seed_id, seed_root)
    try:
        return kernel.get(seed_id)
    except SeedNotFound:
        title = manifest.get("title")
        description = manifest.get("description")
        version = manifest.get("version", "0.1.0")
        if not isinstance(title, str) or not title.strip():
            raise RuntimeSeedError(
                f"Seed manifest for {seed_id!r} requires a non-empty title"
            ) from None
        if not isinstance(description, str) or not description.strip():
            raise RuntimeSeedError(
                f"Seed manifest for {seed_id!r} requires a non-empty description"
            ) from None
        if not isinstance(version, str) or not version.strip():
            raise RuntimeSeedError(
                f"Seed manifest for {seed_id!r} requires a non-empty version"
            ) from None
        return kernel.create_seed(
            title,
            owner,
            description,
            seed_id=seed_id,
            version=version,
        )


def bind_reference_seed(
    kernel: SeedKernel,
    *,
    root: Path | None = None,
) -> RuntimeSeedBinding:
    """Bind the first-party Aethryn SeedLab record to its shipped runtime package."""
    return bind_runtime_seed(kernel, "aethryn", root=root)
