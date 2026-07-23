"""CARD: shelf_pour -- pour the Hardware Store shelf as a standalone installable package.

`cast` pours a GAME; this pours the LIBRARY. It vendors the 27 shelf cores under a FRESH top-level
package (`codeforge_shelf`, no `parts` engine anywhere), auto-detects the third-party deps they
actually import, and writes a `pyproject.toml` that declares them. The result is the vision's second
output made concrete: a Software Hardware Store you can pip-install and import with zero CodeForge
engine present. Because the poured package is renamed, `verify_pour` can prove it in a subprocess
that genuinely cannot reach the engine (importing `parts.shelf` would find the repo;
`codeforge_shelf` can only be the poured copy).

Reads the shelf; writes only inside the destination dir. No engine state is touched.
"""

from __future__ import annotations

import ast
import re
import subprocess  # nosec B404 -- fixed argv, no shell; imports the poured package to prove it loads
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_PKG = "parts.shelf"
PACKAGE = (
    "codeforge_shelf"  # the poured top-level package: deliberately NOT `parts`, so it isolates
)


class ShelfPourError(ValueError):
    """A shelf module could not be read or parsed while pouring. Fail loud: a bad pour is worse."""


@dataclass(frozen=True)
class PouredShelf:
    """The record of a pour: where it went, what package it is, its cores, and its declared deps."""

    path: Path
    package: str
    cores: tuple[str, ...]
    dependencies: tuple[str, ...]


def _core_files(shelf_dir: Path) -> list[Path]:
    return [p for p in sorted(shelf_dir.glob("*.py")) if p.name != "__init__.py"]


def shelf_third_party_deps(shelf_dir: Path | None = None) -> list[str]:
    """The third-party packages the shelf imports (non-stdlib, non-`parts`), sorted + deduped.

    A pour must declare these or the poured package will not import; detected from the AST so the
    list stays honest as cores change (today: fastapi, pydantic, structlog -- from 2 cores)."""
    base = shelf_dir if shelf_dir is not None else _ROOT / "parts" / "shelf"
    stdlib = set(sys.stdlib_module_names)
    deps: set[str] = set()
    for py in _core_files(base):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:
            raise ShelfPourError(f"cannot parse {py}: {exc}") from exc
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name and name not in stdlib and name != "parts":
                    deps.add(name)
    return sorted(deps)


def _rewrite(source: str) -> str:
    """Rebind a core from `parts.shelf` to the poured package name (`codeforge_shelf`)."""
    return re.sub(rf"\b{re.escape(_SOURCE_PKG)}\b", PACKAGE, source)


def _pyproject(deps: list[str]) -> str:
    dep_lines = "".join(f'    "{d}",\n' for d in deps)
    return (
        "[build-system]\n"
        'requires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        f'name = "codeforge-shelf"\n'
        'version = "0.1.0"\n'
        'description = "The CodeForge Hardware Store: reusable, engine-agnostic Python cores."\n'
        'requires-python = ">=3.11"\n'
        "dependencies = [\n"
        f"{dep_lines}"
        "]\n\n"
        "[tool.setuptools]\n"
        f'packages = ["{PACKAGE}"]\n'
    )


def _readme(cores: list[str], deps: list[str]) -> str:
    listing = "\n".join(f"- `{PACKAGE}.{c}`" for c in cores)
    dep_note = ", ".join(deps) if deps else "none (pure stdlib)"
    return (
        "# CodeForge Hardware Store\n\n"
        "Reusable, engine-agnostic Python cores, proven in the CodeForge MUD and poured here as a\n"
        "standalone package. No game engine is required to use them.\n\n"
        f"Third-party dependencies: {dep_note}.\n\n"
        f"## Cores ({len(cores)})\n\n"
        f"{listing}\n"
    )


def pour_shelf(dest: Path, *, shelf_dir: Path | None = None) -> PouredShelf:
    """Vendor the shelf into `dest` as the standalone `codeforge_shelf` package.

    Writes `dest/codeforge_shelf/<core>.py` (imports rebound off `parts`), a `pyproject.toml` that
    declares the auto-detected deps, and a README. Returns a PouredShelf record. Writes only under
    `dest`; reads the live shelf read-only."""
    src = shelf_dir if shelf_dir is not None else _ROOT / "parts" / "shelf"
    cores = _core_files(src)
    if not cores:
        raise ShelfPourError(f"no shelf cores found under {src}")
    deps = shelf_third_party_deps(src)
    dest = Path(dest)
    pkg_dir = dest / PACKAGE
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(
        f'"""The CodeForge Hardware Store, poured standalone from {_SOURCE_PKG}."""\n',
        encoding="utf-8",
    )
    names = [c.stem for c in cores]
    for core in cores:
        (pkg_dir / core.name).write_text(
            _rewrite(core.read_text(encoding="utf-8")), encoding="utf-8"
        )
    (dest / "pyproject.toml").write_text(_pyproject(deps), encoding="utf-8")
    (dest / "README.md").write_text(_readme(names, deps), encoding="utf-8")
    return PouredShelf(path=dest, package=PACKAGE, cores=tuple(names), dependencies=tuple(deps))


def _real_runner(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(  # nosec B603 -- fixed argv (sys.executable), no shell, poured dir only
        cmd, cwd=str(cwd), capture_output=True, text=True
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def verify_pour(dest: Path, *, runner=None) -> tuple[bool, str]:
    """Prove the poured package imports every core with NO engine present; returns `(ok, detail)`.

    Runs a subprocess that imports `codeforge_shelf.<core>` for every core, from `dest`. Renamed off
    `parts`, it can only resolve to the poured copy -- so a clean import proves the shelf stands
    alone. `runner(cmd, cwd) -> (rc, output)` is a seam (default: real subprocess)."""
    run = runner or _real_runner
    dest = Path(dest)
    pkg_dir = dest / PACKAGE
    if not pkg_dir.is_dir():
        return False, f"no poured package at {pkg_dir}"
    cores = [p.stem for p in sorted(pkg_dir.glob("*.py")) if p.name != "__init__.py"]
    prog = (
        "import importlib\n"
        + "\n".join(f"importlib.import_module('{PACKAGE}.{c}')" for c in cores)
        + f"\nprint('imported', {len(cores)}, 'cores standalone')\n"
    )
    rc, out = run([sys.executable, "-c", prog], dest)
    if rc != 0:
        return False, f"standalone import failed: {out.strip()[-200:]}"
    return True, f"imported {len(cores)} cores with no engine present"


def _main(argv: list[str]) -> int:
    """`python3 -m parts.shelf_pour <dest>`: pour the shelf, then prove it imports standalone."""
    dest = Path(argv[1]) if len(argv) > 1 else _ROOT / "workspace" / "shelf-pour"
    poured = pour_shelf(dest)
    ok, detail = verify_pour(dest)
    print(f"poured {len(poured.cores)} cores -> {dest / poured.package}")
    print(f"  package: {poured.package}  deps: {', '.join(poured.dependencies) or '(none)'}")
    print(f"  verify:  {'PASS' if ok else 'FAIL'} - {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))  # pragma: no cover
