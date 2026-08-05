"""Product Seed-selection contract: precedence, persistence, and safe failure."""

import json

import pytest

from kernel.seed_selection import (
    SeedSelectionError,
    clear_persisted_seed,
    persist_seed,
    read_persisted_seed,
    resolve_seed,
)

AVAILABLE = {"aethryn", "first-forge", "spiral-ascent"}


def test_product_default_is_aethryn():
    selection = resolve_seed(available=AVAILABLE)
    assert selection.seed_id == "aethryn"
    assert selection.source == "default"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"explicit": "spiral-ascent", "active_project": "first-forge"}, "spiral-ascent"),
        ({"active_project": "first-forge", "persisted": "spiral-ascent"}, "first-forge"),
        ({"persisted": "spiral-ascent", "environment": "first-forge"}, "spiral-ascent"),
        ({"environment": "first-forge"}, "first-forge"),
    ],
)
def test_precedence_is_explicit_project_persisted_environment_default(kwargs, expected):
    assert resolve_seed(available=AVAILABLE, **kwargs).seed_id == expected


def test_unavailable_configured_seed_fails_without_fallback():
    with pytest.raises(SeedSelectionError, match="not installed"):
        resolve_seed(persisted="removed-seed", available=AVAILABLE)


def test_persisted_selection_is_atomic_and_round_trips(tmp_path):
    path = tmp_path / "preferences" / "selection.json"
    assert persist_seed("spiral-ascent", path) == path
    assert read_persisted_seed(path) == "spiral-ascent"
    assert json.loads(path.read_text()) == {"version": 1, "seed": "spiral-ascent"}
    assert clear_persisted_seed(path) is True
    assert clear_persisted_seed(path) is False


def test_persisted_selection_rejects_malformed_json(tmp_path):
    path = tmp_path / "selection.json"
    path.write_text("[]")
    with pytest.raises(SeedSelectionError, match="must contain"):
        read_persisted_seed(path)
