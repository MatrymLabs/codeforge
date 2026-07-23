"""Test twin for parts/shelf_pour.py -- pouring the shelf as a standalone package.

Acceptance: the live shelf pours into `codeforge_shelf` (renamed off `parts`), declares its real
deps, and -- the whole point -- imports every core in a subprocess with no engine present. Refusal:
an empty shelf fails loud; verify reports a failed import; verify on a missing pour is honest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.shelf_pour import (
    PACKAGE,
    ShelfPourError,
    _main,
    _rewrite,
    poolable_twins,
    pour_shelf,
    shelf_third_party_deps,
    verify_pour,
    verify_pour_build,
    verify_pour_tests,
)


def test_pour_produces_the_standalone_package(tmp_path: Path) -> None:
    poured = pour_shelf(tmp_path)
    assert poured.package == PACKAGE
    assert len(poured.cores) >= 25  # the 27-core shelf (guards against an accidental empty pour)
    pkg = tmp_path / PACKAGE
    assert (pkg / "__init__.py").exists()
    assert (tmp_path / "pyproject.toml").exists() and (tmp_path / "README.md").exists()
    # no engine reference survives the rename: the poured package is truly `parts`-free
    for core in poured.cores:
        assert "parts.shelf" not in (pkg / f"{core}.py").read_text(encoding="utf-8")


def test_the_poured_shelf_imports_standalone(tmp_path: Path) -> None:
    # the reusability proof: pour, then import every core in a subprocess that cannot see the engine
    pour_shelf(tmp_path)
    ok, detail = verify_pour(tmp_path)
    assert ok, detail
    assert "no engine" in detail


def test_third_party_deps_are_detected_from_the_ast() -> None:
    deps = shelf_third_party_deps()
    assert "pydantic" in deps and "fastapi" in deps and "structlog" in deps
    assert "parts" not in deps  # the engine is never a declared dependency


def test_pyproject_declares_the_detected_deps(tmp_path: Path) -> None:
    poured = pour_shelf(tmp_path)
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    for dep in poured.dependencies:
        assert f'"{dep}"' in pyproject


def test_pour_on_an_empty_shelf_fails_loud(tmp_path: Path) -> None:
    empty = tmp_path / "shelf"
    empty.mkdir()
    (empty / "__init__.py").write_text("")
    with pytest.raises(ShelfPourError, match="no shelf cores"):
        pour_shelf(tmp_path / "out", shelf_dir=empty)


def test_verify_reports_a_failed_import(tmp_path: Path) -> None:
    pour_shelf(tmp_path)

    def broken_runner(cmd: list[str], cwd: Path) -> tuple[int, str]:
        return 1, "ModuleNotFoundError: boom"

    ok, detail = verify_pour(tmp_path, runner=broken_runner)
    assert not ok and "boom" in detail


def test_verify_on_a_missing_pour_is_honest(tmp_path: Path) -> None:
    ok, detail = verify_pour(tmp_path)  # nothing poured here
    assert not ok and "no poured package" in detail


def test_rewrite_rebinds_the_package_off_parts() -> None:
    out = _rewrite("from parts.shelf.retry import run\nimport parts.shelf.statemachine\n")
    assert "parts.shelf" not in out
    assert f"from {PACKAGE}.retry import run" in out


def test_pour_ships_the_engine_free_twins_and_holds_the_rest(tmp_path: Path) -> None:
    poured = pour_shelf(tmp_path)
    # the engine-coupled twins are held back, named -- not silently dropped
    assert set(poured.tests_held) == {"console", "observability"}
    assert len(poured.tests) >= 20 and "console" not in poured.tests
    # test deps are auto-declared beyond the runtime deps
    assert "pytest" in poured.test_dependencies
    for name in poured.tests:
        assert (tmp_path / "tests" / f"test_{name}.py").exists()


def test_the_poured_tests_pass_with_no_engine(tmp_path: Path) -> None:
    # the reusability gold standard: the poured library passes its OWN tests, engine absent
    pour_shelf(tmp_path)
    ok, detail = verify_pour_tests(tmp_path)
    assert ok, detail
    assert "no engine present" in detail


def test_poolable_twins_splits_engine_free_from_coupled() -> None:
    poolable, held = poolable_twins()
    assert set(held) == {"console", "observability"}
    assert all(p.name.startswith("test_") for p in poolable)


def test_pyproject_declares_test_extras_and_markers(tmp_path: Path) -> None:
    pour_shelf(tmp_path)
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.optional-dependencies]" in pyproject and '"pytest"' in pyproject
    assert "[tool.pytest.ini_options]" in pyproject  # the property mark is registered


def test_verify_pour_tests_reports_a_failed_run(tmp_path: Path) -> None:
    pour_shelf(tmp_path)

    def failing(cmd: list[str], cwd: Path) -> tuple[int, str]:
        return 1, "1 failed, 3 passed"

    ok, detail = verify_pour_tests(tmp_path, runner=failing)
    assert not ok and "failed" in detail


def test_verify_pour_tests_on_a_pour_without_tests_is_honest(tmp_path: Path) -> None:
    (tmp_path / PACKAGE).mkdir()  # a package dir but no tests/
    ok, detail = verify_pour_tests(tmp_path)
    assert not ok and "no poured tests" in detail


def test_pour_writes_release_metadata_and_license(tmp_path: Path) -> None:
    pour_shelf(tmp_path)
    assert (tmp_path / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    for token in ('license = "MIT"', "authors =", "classifiers =", "[project.urls]", "readme ="):
        assert token in pyproject
    # PEP 639: the SPDX license expression forbids a redundant License classifier
    assert "License :: OSI Approved" not in pyproject


def test_pour_ships_a_py_typed_marker(tmp_path: Path) -> None:
    # the classifier claims Typing :: Typed -- back it with the PEP 561 marker + package-data
    pour_shelf(tmp_path)
    assert (tmp_path / PACKAGE / "py.typed").exists()
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.package-data]" in pyproject and '"py.typed"' in pyproject


def test_pour_writes_a_rich_readme_and_changelog(tmp_path: Path) -> None:
    pour_shelf(tmp_path)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "badge.svg" in readme  # CI/PyPI/license badges
    assert "pip install codeforge-shelf" in readme and "## Usage" in readme
    assert "## Provenance" in readme
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8").startswith("# Changelog")


def test_pour_writes_ci_and_release_workflows(tmp_path: Path) -> None:
    pour_shelf(tmp_path)
    test_wf = tmp_path / ".github" / "workflows" / "test.yml"
    release_wf = tmp_path / ".github" / "workflows" / "release.yml"
    assert "pytest -q" in test_wf.read_text(encoding="utf-8")
    release = release_wf.read_text(encoding="utf-8")
    # Trusted Publishing: OIDC id-token, no stored PyPI token, on a GitHub Release
    assert "id-token: write" in release and "pypa/gh-action-pypi-publish" in release
    assert "release:" in release and "types: [published]" in release


def test_verify_pour_build_orchestrates_build_and_install(tmp_path: Path) -> None:
    pour_shelf(tmp_path)
    work = tmp_path / "work"

    def fake(cmd: list[str], cwd: Path | None) -> tuple[int, str]:
        if "wheel" in cmd:  # simulate pip wheel producing the artifact at its -w target
            dist = Path(cmd[cmd.index("-w") + 1])
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "codeforge_shelf-0.1.0-py3-none-any.whl").write_text("")
        return 0, "ok"

    ok, detail = verify_pour_build(tmp_path, work, runner=fake)
    assert ok and "imported it from a fresh venv" in detail


def test_verify_pour_build_reports_a_failed_step(tmp_path: Path) -> None:
    pour_shelf(tmp_path)

    def fails(cmd: list[str], cwd: Path | None) -> tuple[int, str]:
        return 1, "venv: boom"

    ok, detail = verify_pour_build(tmp_path, tmp_path / "w", runner=fails)
    assert not ok and "boom" in detail


def test_verify_pour_build_needs_a_package(tmp_path: Path) -> None:
    ok, detail = verify_pour_build(tmp_path, tmp_path / "w")  # nothing poured
    assert not ok and "no package to build" in detail


def test_verify_pour_build_flags_a_missing_wheel(tmp_path: Path) -> None:
    pour_shelf(tmp_path)

    def no_wheel(cmd: list[str], cwd: Path | None) -> tuple[int, str]:
        return 0, "ok"  # steps 'succeed' but never create a wheel

    ok, detail = verify_pour_build(tmp_path, tmp_path / "w", runner=no_wheel)
    assert not ok and "no wheel" in detail


def test_verify_pour_build_reports_a_failed_install(tmp_path: Path) -> None:
    pour_shelf(tmp_path)

    def build_ok_install_bad(cmd: list[str], cwd: Path | None) -> tuple[int, str]:
        if "wheel" in cmd:
            dist = Path(cmd[cmd.index("-w") + 1])
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "codeforge_shelf-0.1.0-py3-none-any.whl").write_text("")
        if "install" in cmd:
            return 1, "pip install: resolution impossible"
        return 0, "ok"

    ok, detail = verify_pour_build(tmp_path, tmp_path / "w", runner=build_ok_install_bad)
    assert not ok and "install/import failed" in detail


def test_main_build_subcommand_runs_the_build(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import parts.shelf_pour as sp

    # the real build needs network (pip); stub the verify so the CLI dispatch is covered offline
    monkeypatch.setattr(sp, "verify_pour_build", lambda dest, work, **k: (True, "built a wheel"))
    rc = sp._main(["shelf_pour", "build", str(tmp_path), str(tmp_path / "w")])
    assert rc == 0
    assert "build:   PASS" in capsys.readouterr().out


def test_dep_detection_fails_loud_on_an_unparseable_core(tmp_path: Path) -> None:
    shelf = tmp_path / "shelf"
    shelf.mkdir()
    (shelf / "broken.py").write_text("import (\n")  # not valid Python
    with pytest.raises(ShelfPourError, match="cannot parse"):
        shelf_third_party_deps(shelf)


def _fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A synthetic root with parts/shelf/ + tests/, matching pour_shelf's default layout."""
    shelf = tmp_path / "parts" / "shelf"
    tests = tmp_path / "tests"
    shelf.mkdir(parents=True)
    tests.mkdir()
    (shelf / "__init__.py").write_text("")
    return shelf, tests


def test_a_twin_that_cannot_be_parsed_fails_loud(tmp_path: Path) -> None:
    shelf, tests = _fake_repo(tmp_path)
    (shelf / "widget.py").write_text("x = 1\n")
    (tests / "test_widget.py").write_text("def broken(:\n")  # unparseable twin
    with pytest.raises(ShelfPourError, match="cannot parse"):
        poolable_twins(shelf, tests)


def test_a_core_without_a_twin_is_skipped(tmp_path: Path) -> None:
    shelf, tests = _fake_repo(tmp_path)
    (shelf / "orphan.py").write_text("x = 1\n")  # no test_orphan.py
    poolable, held = poolable_twins(shelf, tests)
    assert poolable == [] and held == []


def test_pour_with_no_poolable_twins_writes_no_tests_dir(tmp_path: Path) -> None:
    shelf, _tests = _fake_repo(tmp_path)
    (shelf / "solo.py").write_text("x = 1\n")  # a core, but no twin anywhere
    poured = pour_shelf(tmp_path / "out", shelf_dir=shelf)
    assert poured.tests == () and not (tmp_path / "out" / "tests").exists()


def test_main_pours_verifies_and_runs_tests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = _main(["shelf_pour", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "imports: PASS" in out and "tests:   PASS" in out
    assert "held" in out  # the honest report of engine-coupled twins
