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
    _rewrite,
    pour_shelf,
    shelf_third_party_deps,
    verify_pour,
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
