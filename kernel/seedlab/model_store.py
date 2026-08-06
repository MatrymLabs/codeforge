"""CARD: model_store -- persist and recover a Seed's extracted project models, and label them for
the Project Hub's `models` facet.

Stage 4 needs an extracted model to be PERSISTED and inspectable after a restart, not just held in
memory. This is that store, mirroring the Seed Kernel's file-backed pattern:

  * `ModelStore`        -- the persistence seam (save / load / all_for_seed).
  * `FileModelStore`    -- one JSON file per model under `<root>/<seed_id>/<model_id>.json`; a fresh
    store over the same root recovers every model (atomic writes).
  * `InMemoryModelStore`-- a volatile store for tests.
  * `model_label` / `model_labels` -- the one-line entries a Seed's models contribute to the Hub's
    `models` facet, each linked back to its source (`<- source_id`) so the model traces to evidence.

Reuses `ProjectModel.to_dict`/`from_dict` for serialization; fails loud on a corrupt record. No
`kernel/world/` coupling. Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session as SqlSession

from kernel.platform_db import SeedModelRow, open_archive_session
from kernel.seedlab.project_model import ProjectModel
from kernel.shelf.atomic_write import atomic_write_text

_SLUG = re.compile(r"[^a-z0-9]+")


class ModelStoreError(Exception):
    """A model record is malformed or corrupt. Fails loud; never loads a lie."""


def model_id_for(model: ProjectModel) -> str:
    """A stable, filesystem-safe id for a model, slugged from its identity."""
    slug = _SLUG.sub("-", model.identity.strip().lower()).strip("-") or "model"
    return f"model-{slug}"[:80]


def model_label(model: ProjectModel) -> str:
    """The one-line entry a model contributes to the Hub's `models` facet, linked to its source."""
    return (
        f"{model.identity} ({len(model.entities)} entities, {len(model.interfaces)} interfaces, "
        f"{len(model.unknowns)} unknowns) <- {model.provenance.source_id}"
    )


@runtime_checkable
class ModelStore(Protocol):
    """The persistence seam for a Seed's project models."""

    def save(self, seed_id: str, model_id: str, model: ProjectModel) -> None: ...

    def load(self, seed_id: str, model_id: str) -> ProjectModel | None: ...

    def all_for_seed(self, seed_id: str) -> list[ProjectModel]: ...


@dataclass
class InMemorySeedModels:
    """A volatile model store keyed by (seed_id, model_id). Does not survive restart, by design."""

    _models: dict[tuple[str, str], ProjectModel] = field(default_factory=dict)

    def save(self, seed_id: str, model_id: str, model: ProjectModel) -> None:
        self._models[(seed_id, model_id)] = model

    def load(self, seed_id: str, model_id: str) -> ProjectModel | None:
        return self._models.get((seed_id, model_id))

    def all_for_seed(self, seed_id: str) -> list[ProjectModel]:
        return [m for (sid, _), m in sorted(self._models.items()) if sid == seed_id]


@dataclass
class FileModelStore:
    """A durable model store: one JSON file per model under `<root>/<seed_id>/`. A fresh store over
    the same root recovers every model, so a Seed's models survive restart."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, seed_id: str) -> Path:
        d = self.root / seed_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, seed_id: str, model_id: str, model: ProjectModel) -> None:
        target = self._dir(seed_id) / f"{model_id}.json"
        atomic_write_text(target, json.dumps(model.to_dict(), indent=2))

    def load(self, seed_id: str, model_id: str) -> ProjectModel | None:
        path = self.root / seed_id / f"{model_id}.json"
        if not path.is_file():
            return None
        try:
            return ProjectModel.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise ModelStoreError(f"corrupt model record {path}: {exc}") from exc

    def all_for_seed(self, seed_id: str) -> list[ProjectModel]:
        seed_dir = self.root / seed_id
        if not seed_dir.is_dir():
            return []
        out: list[ProjectModel] = []
        for path in sorted(seed_dir.glob("*.json")):
            model = self.load(seed_id, path.stem)
            if model is not None:
                out.append(model)
        return out


@dataclass
class SqlModelStore:
    """Durable model store using the platform SQL persistence boundary."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def save(self, seed_id: str, model_id: str, model: ProjectModel) -> None:
        payload = json.dumps(model.to_dict(), sort_keys=True, separators=(",", ":"))
        with self.session_factory() as session, session.begin():
            row = session.get(SeedModelRow, (seed_id, model_id))
            if row is None:
                session.add(SeedModelRow(seed_id=seed_id, model_id=model_id, model_json=payload))
            else:
                row.model_json = payload

    def load(self, seed_id: str, model_id: str) -> ProjectModel | None:
        with self.session_factory() as session:
            row = session.get(SeedModelRow, (seed_id, model_id))
        if row is None:
            return None
        try:
            return ProjectModel.from_dict(json.loads(row.model_json))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ModelStoreError(
                f"corrupt SQL model record {seed_id}/{model_id}: {exc}"
            ) from exc

    def all_for_seed(self, seed_id: str) -> list[ProjectModel]:
        with self.session_factory() as session:
            rows = (
                session.query(SeedModelRow)
                .filter(SeedModelRow.seed_id == seed_id)
                .order_by(SeedModelRow.model_id)
                .all()
            )
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: SeedModelRow) -> ProjectModel:
        try:
            return ProjectModel.from_dict(json.loads(row.model_json))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ModelStoreError(
                f"corrupt SQL model record {row.seed_id}/{row.model_id}: {exc}"
            ) from exc


@dataclass
class DualReadModelStore:
    """Read legacy model files while writing new models to SQL."""

    primary: ModelStore
    legacy: ModelStore

    def save(self, seed_id: str, model_id: str, model: ProjectModel) -> None:
        self.primary.save(seed_id, model_id, model)

    def load(self, seed_id: str, model_id: str) -> ProjectModel | None:
        return self.primary.load(seed_id, model_id) or self.legacy.load(seed_id, model_id)

    def all_for_seed(self, seed_id: str) -> list[ProjectModel]:
        primary = {
            model_id_for(model): model for model in self.primary.all_for_seed(seed_id)
        }
        legacy = {model_id_for(model): model for model in self.legacy.all_for_seed(seed_id)}
        return [
            primary.get(model_id, legacy[model_id])
            for model_id in sorted(primary.keys() | legacy.keys())
        ]


def model_store(backend: str, home: Path) -> ModelStore:
    """Build the model store selected by the shared SeedLab backend setting."""
    if backend == "file":
        return FileModelStore(Path(home) / "models")
    primary = SqlModelStore()
    if backend == "sql":
        return primary
    if backend == "sql-dual-read":
        return DualReadModelStore(primary, FileModelStore(Path(home) / "models"))
    raise ModelStoreError(
        f"unknown model store backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def configured_model_store(home: Path) -> ModelStore:
    """Open the model store selected by the shared SeedLab registry configuration."""
    import os

    backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return model_store(backend, home)


def model_labels(store: ModelStore, seed_id: str) -> tuple[str, ...]:
    """The `models` facet the Project Hub renders for a Seed, one label per persisted model."""
    return tuple(model_label(m) for m in store.all_for_seed(seed_id))
