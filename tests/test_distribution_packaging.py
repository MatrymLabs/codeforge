"""Every package the runtime imports must be inside the built distribution.

WO-S2 (#929) added `from kernel.seam.wire import ...` at module scope in
`adapters/web_gateway.py`. `kernel.seam` was never added to pyproject's `packages`, so it shipped in
no wheel, and the public demo's container died on ImportError at startup when autoDeploy fired.

`make check` stayed green throughout, because the suite imports from the SOURCE TREE where
`kernel/seam/` sits on disk. Nothing installed the distribution and asked whether it still worked.
That is the dominant defect class at the packaging layer: a verdict over a property never measured.

These tests measure the distribution's package list, not a built artifact, so they are fast and need
no network. The build itself is proven in CI by the docker job.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _declared_packages() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(data["tool"]["setuptools"]["packages"])


def _importable_packages_on_disk() -> set[str]:
    """Every directory that is a real Python package under the shipped top-level layers."""
    found: set[str] = set()
    for top in ("kernel", "adapters", "content"):
        base = ROOT / top
        if not (base / "__init__.py").exists():
            continue
        found.add(top)
        for child in sorted(base.rglob("__init__.py")):
            rel = child.parent.relative_to(ROOT)
            found.add(".".join(rel.parts))
    return found


def test_every_package_on_disk_is_declared_or_deliberately_excluded() -> None:
    """The catch-all. A new package directory must be declared or named here as excluded.

    Stated as the invariant rather than as a list of past accidents: a package that exists and is
    not declared cannot be imported from an install, and nothing else in the suite would notice.
    """
    # Excluded ON PURPOSE, each with the reason it does not ship. Adding a name here is a decision
    # a reviewer can see; leaving a package undeclared is an accident nobody can see.
    deliberately_excluded = {
        "kernel.domains",
        "kernel.script_platform",
        "kernel.seedlab",
    }
    undeclared = _importable_packages_on_disk() - _declared_packages() - deliberately_excluded
    assert not undeclared, (
        f"these packages exist on disk but ship in no distribution: {sorted(undeclared)}. "
        "Declare them in pyproject's `packages`, or add them to deliberately_excluded."
    )


@pytest.mark.parametrize(
    "module",
    [
        "kernel.seam",  # WO-S2's wire schema; its absence killed the public demo
        "kernel.shelf",
        "kernel.world",
        "adapters",
    ],
)
def test_the_gateway_s_runtime_imports_are_declared(module: str) -> None:
    """The demo's entry point imports these at module scope. Undeclared means a dead container."""
    assert module in _declared_packages(), (
        f"{module} is imported by the runtime but is absent from pyproject's `packages`, so an "
        "installed wheel would not carry it and the service dies on ImportError at startup"
    )


def test_the_web_gateway_imports_only_declared_packages() -> None:
    """Derived from the gateway's own source, so a NEW import is caught the day it is added."""
    source = (ROOT / "adapters" / "web_gateway.py").read_text(encoding="utf-8")
    declared = _declared_packages()
    offenders = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith(
            ("from kernel", "from adapters", "from content", "import kernel")
        ):
            continue
        target = stripped.split()[1]
        # A module path resolves to its owning package: kernel.seam.wire -> kernel.seam
        parts = target.split(".")
        if not any(".".join(parts[:i]) in declared for i in range(len(parts), 0, -1)):
            offenders.append(target)
    assert not offenders, (
        f"the web gateway imports {offenders}, whose package is not declared in pyproject. "
        "The container would die on ImportError before serving a request."
    )
