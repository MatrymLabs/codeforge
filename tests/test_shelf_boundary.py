"""Test twin for parts/shelf_boundary.py -- the shelf's one-way-dependency gate.

Acceptance: the real, live shelf imports no engine part (the invariant the whole extraction bought).
Refusal: a synthetic shelf with a core that reaches into the engine is caught, named, and reported;
an intra-shelf import and stdlib are allowed; an unparseable core fails loud.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.shelf_boundary import (
    ShelfBoundaryError,
    _parts_imports,
    shelf_boundary_gaps,
    shelf_import_violations,
)


def test_the_live_shelf_imports_no_engine_part() -> None:
    # the invariant, enforced against the real tree: zero shelf -> engine imports
    assert shelf_import_violations() == {}


def test_the_live_ritual_line_is_clean() -> None:
    assert shelf_boundary_gaps() == []


def _shelf(tmp_path: Path) -> Path:
    d = tmp_path / "parts" / "shelf"
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("")
    return d


def test_a_core_reaching_into_the_engine_is_caught(tmp_path: Path) -> None:
    shelf = _shelf(tmp_path)
    (shelf / "leaky.py").write_text(
        "from parts.world.session import SESSIONS\nimport parts.world.db\n"
    )
    violations = shelf_import_violations(shelf)
    assert violations == {"leaky.py": ["parts.world.db", "parts.world.session"]}


def test_intra_shelf_and_stdlib_imports_are_allowed(tmp_path: Path) -> None:
    shelf = _shelf(tmp_path)
    (shelf / "clean.py").write_text(
        "import json\nfrom pathlib import Path\nfrom parts.shelf.statemachine import Fired\n"
    )
    assert shelf_import_violations(shelf) == {}


def test_the_ritual_line_names_the_offender(tmp_path: Path) -> None:
    shelf = _shelf(tmp_path)
    (shelf / "leaky.py").write_text("import parts.world.combat\n")
    lines = shelf_boundary_gaps(tmp_path)
    assert lines == ["leaky.py: imports engine part(s) parts.world.combat"]


def test_bare_parts_import_counts_as_engine(tmp_path: Path) -> None:
    # `from parts import x` pulls the engine package itself -> a violation, not a shelf import
    shelf = _shelf(tmp_path)
    (shelf / "leaky.py").write_text("from parts import db\n")
    assert "leaky.py" in shelf_import_violations(shelf)


def test_an_unparseable_core_fails_loud(tmp_path: Path) -> None:
    shelf = _shelf(tmp_path)
    (shelf / "broken.py").write_text("def oops(:\n")
    with pytest.raises(ShelfBoundaryError, match="cannot parse"):
        shelf_import_violations(shelf)


def test_parts_import_extractor_finds_both_forms() -> None:
    mods = _parts_imports(
        "import parts.world.db\nfrom parts.shelf.retry import run\nfrom parts import x\n", "<t>"
    )
    assert mods == {"parts.world.db", "parts.shelf.retry", "parts"}
