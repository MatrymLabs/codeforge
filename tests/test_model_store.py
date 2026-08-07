"""Test twin for kernel/seedlab/model_store.py -- persistence of a Seed's extracted models.

Acceptance: a model round-trips through the in-memory store; a file store recovers every model after
a restart; labels link a model to its source and list per Seed.

Refusal: a missing model loads as None; a corrupt record raises rather than loading a lie.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kernel.seedlab.model_store import (
    DualReadModelStore,
    FileModelStore,
    InMemorySeedModels,
    ModelStore,
    ModelStoreError,
    SqlModelStore,
    model_id_for,
    model_label,
    model_labels,
)
from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.world.db import ArchiveBase


def _model(identity: str = "TaskLedger", src: str = "demo-src") -> ProjectModel:
    return ProjectModel(
        identity=identity,
        provenance=Provenance(src, owner="josh", license="MIT", visibility="private"),
        entities=["Task", "Ledger"],
        interfaces=["pyproject.toml", "script:tl"],
        unknowns=["identity read from pyproject.toml", "no behavioral analysis performed"],
    )


# --- acceptance --------------------------------------------------------------------------------
def test_model_id_is_slugged() -> None:
    assert model_id_for(_model("My Cool CLI!")) == "model-my-cool-cli"


def test_label_links_to_source() -> None:
    label = model_label(_model())
    assert "TaskLedger" in label and "2 entities" in label and "<- demo-src" in label


def test_a_store_is_a_model_store() -> None:
    assert isinstance(InMemorySeedModels(), ModelStore)


def test_inmemory_roundtrip() -> None:
    store = InMemorySeedModels()
    m = _model()
    store.save("seed-1", model_id_for(m), m)
    assert store.load("seed-1", model_id_for(m)) == m
    assert store.all_for_seed("seed-1") == [m]


def test_file_store_survives_restart(tmp_path: Path) -> None:
    m = _model()
    FileModelStore(tmp_path / "models").save("seed-1", model_id_for(m), m)
    # Restart: a brand-new store object over the same root recovers the model intact.
    recovered = FileModelStore(tmp_path / "models").all_for_seed("seed-1")
    assert recovered == [m]


def test_sql_store_survives_restart(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    model = _model()
    model_id = model_id_for(model)
    SqlModelStore(lambda: Session(engine)).save("seed-1", model_id, model)

    recovered = SqlModelStore(lambda: Session(engine)).all_for_seed("seed-1")

    assert recovered == [model]


def test_dual_read_model_store_writes_sql_and_reads_legacy(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'platform.db'}")
    ArchiveBase.metadata.create_all(engine)
    home = tmp_path / "models"
    model = _model()
    model_id = model_id_for(model)
    legacy = FileModelStore(home)
    legacy.save("seed-1", model_id, model)
    store = DualReadModelStore(
        SqlModelStore(lambda: Session(engine)),
        legacy,
    )

    assert store.load("seed-1", model_id) == model
    replacement = _model("Replacement")
    store.save("seed-1", model_id_for(replacement), replacement)
    assert (
        SqlModelStore(lambda: Session(engine)).load("seed-1", model_id_for(replacement))
        == replacement
    )


def test_model_labels_lists_all_for_a_seed() -> None:
    store = InMemorySeedModels()
    for ident in ("Alpha", "Beta"):
        m = _model(ident)
        store.save("seed-1", model_id_for(m), m)
    store.save("seed-2", "model-x", _model("Other"))  # a different Seed's model is not listed
    labels = model_labels(store, "seed-1")
    assert len(labels) == 2 and any("Alpha" in x for x in labels)


# --- refusal -----------------------------------------------------------------------------------
def test_missing_model_loads_none() -> None:
    assert InMemorySeedModels().load("seed-1", "nope") is None
    assert FileModelStore.__mro__  # sanity: class exists


def test_all_for_seed_empty_when_absent(tmp_path: Path) -> None:
    assert FileModelStore(tmp_path / "m").all_for_seed("seed-unknown") == []


def test_corrupt_record_raises(tmp_path: Path) -> None:
    store = FileModelStore(tmp_path / "models")
    seed_dir = store.root / "seed-1"
    seed_dir.mkdir(parents=True)
    (seed_dir / "model-bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ModelStoreError, match="corrupt"):
        store.load("seed-1", "model-bad")
