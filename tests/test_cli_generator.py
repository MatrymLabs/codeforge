"""Test twin for parts/seedlab/cli_generator.py -- generate a runnable CLI target from a model.

Acceptance: generation emits a runnable layout with checksums + provenance; it is reproducible (same
model -> same manifest hash); the generated target RUNS (`--version`) and its generated TESTS PASS
(both proven through the Stage-5 runner); the full Stage 4 -> 6 flow works from a real source; and
rollback cleans up.

Refusal: an empty identity and a non-empty destination are refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.seedlab.cli_generator import (
    GeneratedArtifact,
    GeneratorError,
    generate_cli,
    render_artifact,
    rollback,
    validate_runs,
    validate_tests,
)
from parts.seedlab.project_model import ProjectModel, Provenance
from parts.seedlab.source_connector import LocalSource


def _model(
    identity: str = "task-ledger", actions: tuple[str, ...] = ("add", "complete")
) -> ProjectModel:
    return ProjectModel(
        identity=identity,
        provenance=Provenance("demo-src", owner="josh", license="MIT", visibility="private"),
        actions=list(actions),
    )


# --- acceptance --------------------------------------------------------------------------------
def test_generate_emits_a_runnable_layout(tmp_path: Path) -> None:
    art = generate_cli(_model(), tmp_path / "out")
    assert art.package == "task_ledger" and art.name == "task-ledger"
    assert "task_ledger/__main__.py" in art.files and "tests/test_cli.py" in art.files
    assert set(art.checksums) == set(art.files) and art.manifest_hash
    assert art.provenance.source_id == "demo-src" and art.commands == ["add", "complete"]
    assert (tmp_path / "out" / "task_ledger" / "__main__.py").is_file()


def test_generation_is_reproducible(tmp_path: Path) -> None:
    a = generate_cli(_model(), tmp_path / "a")
    b = generate_cli(_model(), tmp_path / "b")
    assert a.manifest_hash == b.manifest_hash and a.checksums == b.checksums


def test_the_generated_target_runs(tmp_path: Path) -> None:
    art = generate_cli(_model(), tmp_path / "out")
    result = validate_runs(art)
    assert result.ok and "0.1.0" in result.output  # --version prints the version


def test_the_generated_tests_pass(tmp_path: Path) -> None:
    art = generate_cli(_model(), tmp_path / "out")
    result = validate_tests(art)
    assert result.ok, result.output  # the target's own generated suite passes


def test_default_command_when_model_has_no_actions(tmp_path: Path) -> None:
    art = generate_cli(_model(actions=()), tmp_path / "out")
    assert art.commands == ["info"]
    assert validate_runs(art).ok


def test_identity_with_symbols_yields_a_valid_package(tmp_path: Path) -> None:
    art = generate_cli(_model(identity="My Cool CLI!"), tmp_path / "out")
    assert art.package == "my_cool_cli" and art.name == "my-cool-cli"
    assert validate_runs(art).ok


def test_full_flow_from_a_source(tmp_path: Path) -> None:
    # Stage 4 -> 6: model a real source, then generate + run a CLI from that model.
    from parts.seedlab.source_modeler import model_from_source

    src_root = tmp_path / "proj"
    (src_root / "widget").mkdir(parents=True)
    (src_root / "widget" / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "pyproject.toml").write_text("[project]\nname = 'widget'\n", encoding="utf-8")
    model = model_from_source(LocalSource(src_root, Provenance("widget-src", owner="josh")))

    art = generate_cli(model, tmp_path / "out")
    assert art.name == "widget"
    assert validate_runs(art).ok


def test_rollback_removes_the_tree(tmp_path: Path) -> None:
    art = generate_cli(_model(), tmp_path / "out")
    rollback(art)
    assert not (tmp_path / "out").exists()
    rollback(art)  # idempotent


def test_render_artifact_summarizes(tmp_path: Path) -> None:
    text = render_artifact(generate_cli(_model(), tmp_path / "out"))
    assert "task-ledger" in text and "manifest sha" in text and "demo-src" in text


# --- refusal -----------------------------------------------------------------------------------
def test_empty_identity_is_refused(tmp_path: Path) -> None:
    bad = ProjectModel(identity="   ", provenance=Provenance("s"))
    with pytest.raises(GeneratorError, match="identity"):
        generate_cli(bad, tmp_path / "out")


def test_a_non_empty_destination_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "existing.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(GeneratorError, match="not empty"):
        generate_cli(_model(), dest)


def test_artifact_is_a_frozen_record(tmp_path: Path) -> None:
    art = generate_cli(_model(), tmp_path / "out")
    assert isinstance(art, GeneratedArtifact)


def test_identity_that_slugs_to_nothing_is_refused(tmp_path: Path) -> None:
    with pytest.raises(GeneratorError, match="empty identity"):
        generate_cli(_model(identity="!!!"), tmp_path / "out")


def test_identity_starting_with_a_digit_gets_a_prefix(tmp_path: Path) -> None:
    art = generate_cli(_model(identity="123 tool"), tmp_path / "out")
    assert art.package == "app_123_tool"  # a valid Python identifier
    assert validate_runs(art).ok
