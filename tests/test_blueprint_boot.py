"""Boot every shipped Blueprint in an isolated interpreter."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from kernel.world.seed import BLUEPRINTS_ROOT

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BLUEPRINTS = sorted(path for path in BLUEPRINTS_ROOT.iterdir() if path.is_dir())


def _blueprint_case(path: Path) -> object:
    if path.name == "seam-probe":
        return pytest.param(
            path,
            marks=pytest.mark.xfail(
                reason="seam-probe is a differential fixture, not a shipped world"
            ),
            id=path.name,
        )
    return pytest.param(path, id=path.name)


@pytest.mark.parametrize("blueprint", [_blueprint_case(path) for path in _BLUEPRINTS])
def test_blueprint_boots_in_a_clean_interpreter(blueprint: Path) -> None:
    """Each discovered Blueprint must pass the engine's module-level boot gate."""
    environment = os.environ.copy()
    environment["FORGE_BLUEPRINT"] = blueprint.name
    result = subprocess.run(
        [sys.executable, "-c", "import forge"],
        cwd=_REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Blueprint {blueprint.name!r} failed to boot.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
