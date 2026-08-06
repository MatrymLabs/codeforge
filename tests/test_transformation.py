"""Acceptance tests for the explicit ProjectModel-to-CLI transformation proof."""

from __future__ import annotations

import pytest

from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.transformation import (
    CLI_PROJECT_TO_TARGET,
    TransformationError,
    transform_project_to_cli,
)


def _model(**kwargs: object) -> ProjectModel:
    values: dict[str, object] = {
        "identity": "task-ledger",
        "provenance": Provenance("demo-src", owner="josh", license="MIT"),
        "actions": ["Add Item", "complete"],
    }
    values.update(kwargs)
    return ProjectModel(**values)  # type: ignore[arg-type]


def test_transformation_is_explicit_versioned_and_deterministic() -> None:
    first = transform_project_to_cli(_model())
    second = transform_project_to_cli(_model())

    assert first.spec == CLI_PROJECT_TO_TARGET
    assert first.spec.source_model_type == "ProjectModel"
    assert first.spec.target_model_type == "CliTargetModel"
    assert first.target.commands == ("add_item", "complete")
    assert first.source_model_digest == second.source_model_digest
    assert first.target_model_digest == second.target_model_digest
    assert first.to_dict() == second.to_dict()


def test_transformation_records_diagnostics_without_hiding_unknowns() -> None:
    result = transform_project_to_cli(_model(actions=[], unknowns=["deployment target"]))

    assert result.target.commands == ("info",)
    assert any("default info" in message for message in result.diagnostics)
    assert any("unresolved unknown" in message for message in result.diagnostics)


def test_transformation_rejects_non_project_models() -> None:
    with pytest.raises(TransformationError, match="ProjectModel"):
        transform_project_to_cli(object())  # type: ignore[arg-type]


def test_transformation_rejects_non_string_actions() -> None:
    with pytest.raises(TransformationError, match="actions"):
        transform_project_to_cli(_model(actions=["ok", 3]))  # type: ignore[list-item]
