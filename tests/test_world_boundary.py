"""Test twin for parts/world_boundary.py -- the World Package's one-way-dependency gate.

Acceptance: the live World Package (parts/world/) imports no platform module (the Layer-1/2
separation the recon found, now physically enforced). Completeness: parts/world/ really is the
transitive closure of the game seed -- no orphan module filed there, none missing. Refusal: a
synthetic world module reaching into the platform is caught and named; a world/shelf import is
allowed; an unparseable module fails loud.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from parts.world_boundary import (
    WORLD_MODULES,
    WorldBoundaryError,
    _is_platform,
    _parts_imports,
    world_boundary_gaps,
    world_import_violations,
)

_ROOT = Path(__file__).resolve().parent.parent
_WORLD = _ROOT / "parts" / "world"

# The game runtime's entry points. The World Package (parts/world/) is their parts-closure;
# the directory must equal that closure, or a new game module would escape the boundary check.
_GAME_SEED = {
    "world",
    "rooms",
    "items",
    "npcs",
    "doors",
    "combat",
    "abilities",
    "jobs",
    "progression",
    "accounts",
    "characters",
    "character_view",
    "zones",
    "equipment",
    "derived",
    "score_sheet",
    "aggression",
    "session",
    "seed",
    "db",
    "events",
    "ranks",
    "engineer",
    "quest",
    "chime",
}


def test_the_live_world_imports_no_platform_module() -> None:
    # the invariant, enforced against the real tree: zero world -> platform imports
    assert world_import_violations() == {}


def test_the_live_ritual_line_is_clean() -> None:
    assert world_boundary_gaps() == []


def test_world_modules_is_the_real_closure_of_the_game_seed() -> None:
    # Completeness: recompute the game closure from source and confirm the parts/world/ directory
    # matches it, so an orphan platform module cannot hide in the world folder and no game module
    # can go missing. Intra-world edges are `parts.world.X` imports.
    def imports_of(mod: str) -> set[str]:
        f = _WORLD / f"{mod}.py"
        if not f.is_file():
            return set()
        out: set[str] = set()
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = []
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("parts."):
                names = [n.module]
            elif isinstance(n, ast.Import):
                names = [a.name for a in n.names if a.name.startswith("parts.")]
            for name in names:
                comps = name.split(".")
                if len(comps) >= 3 and comps[1] == "world":
                    out.add(comps[2])
        return out

    # seed only from game modules that are real files (e.g. 'rooms' is data inside world/seed,
    # not a parts/world/rooms.py), matching how the dir is the closure of EXISTING modules.
    closure = {m for m in _GAME_SEED if (_WORLD / f"{m}.py").is_file()}
    frontier = set(closure)
    while frontier:
        for dep in imports_of(frontier.pop()):
            if dep not in closure and (_WORLD / f"{dep}.py").is_file():
                closure.add(dep)
                frontier.add(dep)
    assert closure == set(WORLD_MODULES)


def test_a_world_module_reaching_into_the_platform_is_caught(tmp_path: Path) -> None:
    world = tmp_path / "parts" / "world"
    world.mkdir(parents=True)
    # 'combat' is a World module; make it import the platform (cast, pm) + the shelf (allowed)
    (world / "combat.py").write_text(
        "from parts.cast import pour_shelf\nfrom parts.shelf.retry import run\nimport parts.pm\n"
    )
    violations = world_import_violations(tmp_path)
    assert violations == {"combat": ["cast", "pm"]}  # shelf import is not a violation


def test_intra_world_and_shelf_imports_are_allowed(tmp_path: Path) -> None:
    world = tmp_path / "parts" / "world"
    world.mkdir(parents=True)
    (world / "combat.py").write_text(
        "from parts.world.world import WORLD\nfrom parts.shelf.statemachine import Fired\n"
        "import json\n"
    )
    assert world_import_violations(tmp_path) == {}


def test_the_ritual_line_names_the_offender(tmp_path: Path) -> None:
    world = tmp_path / "parts" / "world"
    world.mkdir(parents=True)
    (world / "jobs.py").write_text("import parts.veritas\n")
    assert world_boundary_gaps(tmp_path) == ["jobs: imports platform part(s) veritas"]


def test_is_platform_classifies_correctly() -> None:
    assert _is_platform("cast") and _is_platform("veritas")  # dev-tools
    assert not _is_platform("shelf")  # Layer 3
    assert not _is_platform("combat")  # a World module


def test_parts_import_extractor_handles_world_shelf_and_platform() -> None:
    mods = _parts_imports(
        "import parts.cast\nfrom parts.shelf.retry import run\n"
        "from parts.world.combat import hit\n",
        "<t>",
    )
    assert mods == {"cast", "shelf", "combat"}  # platform, shelf, intra-world (unwrapped)


def test_an_unparseable_module_fails_loud() -> None:
    with pytest.raises(WorldBoundaryError, match="cannot parse"):
        _parts_imports("def oops(:\n", "<t>")
