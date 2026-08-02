"""Test twin for kernel/seedlab/web_api_generator.py -- generate a runnable web-API target.

Acceptance: generation emits a runnable WSGI layout with checksums + provenance; it is reproducible
(same model -> same manifest hash); the generated target RUNS (`--check` builds the app and lists
routes, exit 0, no port bound) and its generated TESTS PASS (both through the Stage-5 runner);
routes derive from the model's actions with an `info` default; and rollback cleans up.

Refusal: an empty identity and a non-empty destination are refused. The reserved `health` route can
never be shadowed by a model action.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.project_model import ProjectModel, Provenance
from kernel.seedlab.web_api_generator import (
    GeneratorError,
    generate_web_api,
    render_artifact,
    rollback,
    validate_runs,
    validate_tests,
)


def _model(
    identity: str = "task-ledger", actions: tuple[str, ...] = ("list", "create")
) -> ProjectModel:
    return ProjectModel(
        identity=identity,
        provenance=Provenance("demo-src", owner="josh", license="MIT", visibility="private"),
        actions=list(actions),
    )


# --- acceptance --------------------------------------------------------------------------------
def test_generate_emits_a_runnable_wsgi_layout(tmp_path: Path) -> None:
    art = generate_web_api(_model(), tmp_path / "out")
    assert art.package == "task_ledger" and art.name == "task-ledger"
    assert "task_ledger/app.py" in art.files and "tests/test_api.py" in art.files
    assert set(art.checksums) == set(art.files) and art.manifest_hash
    assert art.provenance.source_id == "demo-src" and art.commands == ["list", "create"]
    assert (tmp_path / "out" / "task_ledger" / "app.py").is_file()


def test_generation_is_reproducible(tmp_path: Path) -> None:
    a = generate_web_api(_model(), tmp_path / "a")
    b = generate_web_api(_model(), tmp_path / "b")
    assert a.manifest_hash == b.manifest_hash and a.checksums == b.checksums


def test_routes_default_to_info_when_the_model_has_no_actions(tmp_path: Path) -> None:
    art = generate_web_api(_model(actions=()), tmp_path / "out")
    assert art.commands == ["info"]


def test_a_model_action_cannot_shadow_the_reserved_health_route(tmp_path: Path) -> None:
    art = generate_web_api(_model(actions=("health", "status")), tmp_path / "out")
    assert "health" not in art.commands and art.commands == ["status"]


def test_the_generated_target_runs(tmp_path: Path) -> None:
    # The real payoff: --check builds the WSGI app and lists routes through the Stage-5 runner,
    # exit 0, WITHOUT binding a port. The vertical slice closes on itself.
    art = generate_web_api(_model(), tmp_path / "out")
    result = validate_runs(art)
    assert result.ok, result.output
    assert "/health" in result.output and "/list" in result.output


def test_the_generated_targets_tests_pass(tmp_path: Path) -> None:
    art = generate_web_api(_model(), tmp_path / "out")
    result = validate_tests(art)
    assert result.ok, result.output  # the emitted pytest suite (WSGI calls, no socket) passes


def test_rollback_removes_the_generated_tree(tmp_path: Path) -> None:
    art = generate_web_api(_model(), tmp_path / "out")
    assert Path(art.dest).exists()
    rollback(art)
    assert not Path(art.dest).exists()
    rollback(art)  # idempotent


def test_render_names_the_routes(tmp_path: Path) -> None:
    art = generate_web_api(_model(), tmp_path / "out")
    text = render_artifact(art)
    assert "web API" in text and "/list" in text and art.package in text


# --- refusal -----------------------------------------------------------------------------------
def test_an_empty_identity_is_refused(tmp_path: Path) -> None:
    with pytest.raises(GeneratorError, match="identity"):
        generate_web_api(_model(identity="   "), tmp_path / "out")


def test_a_non_empty_destination_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(GeneratorError, match="not empty"):
        generate_web_api(_model(), dest)
