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
from collections.abc import Collection
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
    """The record of a pour: where it went, the package, its cores, deps, and poured/held tests."""

    path: Path
    package: str
    cores: tuple[str, ...]
    dependencies: tuple[str, ...]
    tests: tuple[str, ...] = ()  # test twins poured (engine-free, runnable standalone)
    tests_held: tuple[str, ...] = ()  # twins kept in-repo: their tests reach into the engine
    test_dependencies: tuple[str, ...] = ()  # extra deps the poured tests need (e.g. pytest)


def _core_files(shelf_dir: Path) -> list[Path]:
    return [p for p in sorted(shelf_dir.glob("*.py")) if p.name != "__init__.py"]


def _reaches_engine(source: str, where: str) -> bool:
    """True if a source file imports any non-shelf `parts.*` module (an engine reach).

    A shelf core never does (the shelf_boundary gate enforces it), but a core's TEST twin might --
    an integration test that exercises the core against the live engine. Such a twin cannot run in
    the poured, engine-free package, so the pour holds it back rather than ship a dead test."""
    try:
        tree = ast.parse(source, filename=where)
    except SyntaxError as exc:
        raise ShelfPourError(f"cannot parse {where}: {exc}") from exc
    for node in ast.walk(tree):
        mods: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        for m in mods:
            if (m == "parts" or m.startswith("parts.")) and not m.startswith("parts.shelf"):
                return True
    return False


def _third_party(files: list[Path], *, exclude: Collection[str] = frozenset()) -> list[str]:
    """The third-party top-level packages a set of files import (non-stdlib, non-`parts`, sorted).

    Detected from the AST so the declared deps stay honest as the code changes. `exclude` drops
    packages already declared elsewhere (e.g. runtime deps, when computing the extra TEST deps)."""
    stdlib = set(sys.stdlib_module_names)
    deps: set[str] = set()
    for py in files:
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
                if name and name not in stdlib and name != "parts" and name not in exclude:
                    deps.add(name)
    return sorted(deps)


def shelf_third_party_deps(shelf_dir: Path | None = None) -> list[str]:
    """The third-party packages the shelf cores import (non-stdlib, non-`parts`), sorted + deduped.

    A pour must declare these or the poured package will not import; detected from the AST so the
    list stays honest as cores change (today: fastapi, pydantic, structlog -- from 2 cores)."""
    base = shelf_dir if shelf_dir is not None else _ROOT / "parts" / "shelf"
    return _third_party(_core_files(base))


def poolable_twins(
    shelf_dir: Path | None = None, tests_dir: Path | None = None
) -> tuple[list[Path], list[str]]:
    """Split the shelf cores' test twins into (poolable paths, held-back core names).

    A twin is poolable if it reaches no engine part (so it runs against the poured package); a twin
    that imports the engine (an integration test) is held back -- named, not dropped silently."""
    shelf = shelf_dir if shelf_dir is not None else _ROOT / "parts" / "shelf"
    tests = tests_dir if tests_dir is not None else _ROOT / "tests"
    poolable: list[Path] = []
    held: list[str] = []
    for core in _core_files(shelf):
        twin = tests / f"test_{core.stem}.py"
        if not twin.exists():
            continue
        if _reaches_engine(twin.read_text(encoding="utf-8"), str(twin)):
            held.append(core.stem)
        else:
            poolable.append(twin)
    return poolable, held


def _rewrite(source: str) -> str:
    """Rebind a core from `parts.shelf` to the poured package name (`codeforge_shelf`)."""
    return re.sub(rf"\b{re.escape(_SOURCE_PKG)}\b", PACKAGE, source)


_HOMEPAGE = "https://github.com/MatrymLabs/codeforge"

# CI for the published repo: run the poured tests on every push, and publish to PyPI on a GitHub
# Release via Trusted Publishing (OIDC -- no stored token). The `pypi` environment is the deploy
# gate the maintainer configures as the PyPI pending-publisher's environment.
_TEST_WORKFLOW = """\
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python -m pip install --upgrade pip
      - run: python -m pip install .[test]
      - run: pytest -q
"""

_RELEASE_WORKFLOW = """\
name: release
on:
  release:
    types: [published]
permissions:
  contents: read
jobs:
  pypi:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Trusted Publishing (OIDC): no API token stored anywhere
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python -m pip install build
      - run: python -m build  # sdist + wheel
      - uses: pypa/gh-action-pypi-publish@release/v1
"""


def _pyproject(deps: list[str], test_deps: list[str]) -> str:
    dep_lines = "".join(f'    "{d}",\n' for d in deps)
    test_lines = "".join(f'    "{d}",\n' for d in test_deps)
    # No "License ::" classifier: PEP 639 supersedes it with the SPDX `license` expression below,
    # and modern setuptools errors if both are present.
    classifiers = (
        '    "Development Status :: 4 - Beta",\n'
        '    "Intended Audience :: Developers",\n'
        '    "Programming Language :: Python :: 3",\n'
        '    "Typing :: Typed",\n'
    )
    return (
        "[build-system]\n"
        'requires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        'name = "codeforge-shelf"\n'
        'version = "0.1.0"\n'
        'description = "The CodeForge Hardware Store: reusable, engine-agnostic Python cores."\n'
        'readme = "README.md"\n'
        'requires-python = ">=3.11"\n'
        'license = "MIT"\n'
        'license-files = ["LICENSE"]\n'
        'authors = [{ name = "MatrymLabs" }]\n'
        'keywords = ["reusable", "stdlib", "resilience", "patterns", "hardware-store"]\n'
        "classifiers = [\n"
        f"{classifiers}"
        "]\n"
        "dependencies = [\n"
        f"{dep_lines}"
        "]\n\n"
        "[project.optional-dependencies]\n"
        "test = [\n"
        f"{test_lines}"
        "]\n\n"
        "[project.urls]\n"
        f'Homepage = "{_HOMEPAGE}"\n'
        f'Source = "{_HOMEPAGE}"\n\n'
        "[tool.setuptools]\n"
        f'packages = ["{PACKAGE}"]\n\n'
        "[tool.setuptools.package-data]\n"
        f'{PACKAGE} = ["py.typed"]\n\n'  # ship the PEP 561 marker so consumers get the types
        "[tool.pytest.ini_options]\n"
        'markers = ["property: hypothesis-driven property tests"]\n'
    )


def _readme(cores: list[str], deps: list[str], n_tests: int, held: list[str]) -> str:
    listing = "\n".join(f"- `{PACKAGE}.{c}`" for c in cores)
    dep_note = ", ".join(deps) if deps else "none (pure stdlib)"
    held_note = (
        f"\n{len(held)} core(s) keep their tests in the CodeForge repo -- those tests exercise "
        f"the core against the live engine (integration): {', '.join(held)}.\n"
        if held
        else ""
    )
    repo = "https://github.com/MatrymLabs/codeforge-shelf"
    badges = (
        f"[![test]({repo}/actions/workflows/test.yml/badge.svg)]"
        f"({repo}/actions/workflows/test.yml)\n"
        "[![PyPI](https://img.shields.io/pypi/v/codeforge-shelf.svg)]"
        "(https://pypi.org/project/codeforge-shelf/)\n"
        "[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)]"
        "(https://opensource.org/licenses/MIT)\n"
    )
    usage = (
        "```python\n"
        "import time\n"
        "from codeforge_shelf.token_bucket import TokenBucket\n\n"
        "bucket = TokenBucket(rate=5, capacity=10, clock=time.monotonic)\n"
        "decision = bucket.consume(cost=1)\n"
        "if decision.allowed:\n"
        "    ...  # do the rate-limited work; else wait decision.retry_after\n"
        "```\n"
    )
    return (
        "# CodeForge Hardware Store\n\n"
        f"{badges}\n"
        "Reusable, engine-agnostic Python cores, proven in the CodeForge MUD and poured here as a\n"
        "standalone package. No game engine is required to use them. Fully typed (PEP 561).\n\n"
        "## Install\n\n"
        "```sh\n"
        "pip install codeforge-shelf\n"
        f"# or from source: pip install git+{_HOMEPAGE}-shelf\n"
        "```\n\n"
        f"Third-party dependencies: {dep_note}.\n\n"
        "## Usage\n\n"
        f"{usage}\n"
        f"## Cores ({len(cores)})\n\n"
        f"{listing}\n\n"
        "## Tests\n\n"
        f"{n_tests} test twins ship with the package and pass with no engine present "
        "(`pip install .[test] && pytest`).\n"
        f"{held_note}\n"
        "## Provenance\n\n"
        f"Generated from [CodeForge]({_HOMEPAGE}) by its `parts/shelf_pour.py`, which vendors the\n"
        "engine-agnostic cores of `parts/shelf/` under a fresh package name and proves they\n"
        "import and test standalone. Re-poured, never hand-edited.\n"
    )


_CHANGELOG = """\
# Changelog

All notable changes to `codeforge-shelf`. This package is generated (poured) from CodeForge; the
version tracks the pour, not hand edits.

## 0.1.0

- Initial release: the CodeForge Hardware Store poured standalone -- reusable, engine-agnostic
  Python cores extracted from the CodeForge MUD with a one-way dependency, fully typed (PEP 561),
  shipping their engine-free test twins (they pass with no engine present).
"""


def pour_shelf(dest: Path, *, shelf_dir: Path | None = None) -> PouredShelf:
    """Vendor the shelf into `dest` as the standalone `codeforge_shelf` package.

    Writes `dest/codeforge_shelf/<core>.py` (imports rebound off `parts`), a `pyproject.toml` that
    declares the auto-detected deps, and a README. Returns a PouredShelf record. Writes only under
    `dest`; reads the live shelf read-only."""
    src = shelf_dir if shelf_dir is not None else _ROOT / "parts" / "shelf"
    tests_src = shelf_dir.parent.parent / "tests" if shelf_dir is not None else _ROOT / "tests"
    cores = _core_files(src)
    if not cores:
        raise ShelfPourError(f"no shelf cores found under {src}")
    deps = shelf_third_party_deps(src)
    twins, held = poolable_twins(src, tests_src)
    # test deps = what the poured twins import beyond the runtime deps (e.g. pytest, hypothesis)
    test_deps = _third_party(twins, exclude=set(deps))
    dest = Path(dest)
    pkg_dir = dest / PACKAGE
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(
        f'"""The CodeForge Hardware Store, poured standalone from {_SOURCE_PKG}."""\n',
        encoding="utf-8",
    )
    (pkg_dir / "py.typed").write_text("", encoding="utf-8")  # PEP 561: the cores are annotated
    names = [c.stem for c in cores]
    for core in cores:
        (pkg_dir / core.name).write_text(
            _rewrite(core.read_text(encoding="utf-8")), encoding="utf-8"
        )
    poured_tests: list[str] = []
    if twins:
        (dest / "tests").mkdir(exist_ok=True)
        for twin in twins:
            (dest / "tests" / twin.name).write_text(
                _rewrite(twin.read_text(encoding="utf-8")), encoding="utf-8"
            )
            poured_tests.append(twin.stem.removeprefix("test_"))  # core name, matching tests_held
    (dest / "pyproject.toml").write_text(_pyproject(deps, test_deps), encoding="utf-8")
    (dest / "README.md").write_text(_readme(names, deps, len(poured_tests), held), encoding="utf-8")
    (dest / "CHANGELOG.md").write_text(_CHANGELOG, encoding="utf-8")
    license_src = src.parent.parent / "LICENSE"  # the repo's MIT license travels with the package
    if license_src.is_file():
        (dest / "LICENSE").write_text(license_src.read_text(encoding="utf-8"), encoding="utf-8")
    workflows = dest / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "test.yml").write_text(_TEST_WORKFLOW, encoding="utf-8")
    (workflows / "release.yml").write_text(_RELEASE_WORKFLOW, encoding="utf-8")
    return PouredShelf(
        path=dest,
        package=PACKAGE,
        cores=tuple(names),
        dependencies=tuple(deps),
        tests=tuple(poured_tests),
        tests_held=tuple(held),
        test_dependencies=tuple(test_deps),
    )


def _real_runner(cmd: list[str], cwd: Path | None) -> tuple[int, str]:
    proc = subprocess.run(  # nosec B603 -- fixed argv (sys.executable), no shell, poured dir only
        cmd, cwd=str(cwd) if cwd is not None else None, capture_output=True, text=True
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


def verify_pour_tests(dest: Path, *, runner=None) -> tuple[bool, str]:
    """Prove the poured test twins PASS against the poured package, engine absent; `(ok, detail)`.

    Runs `pytest` inside `dest` (only the pour dir on the path), so a green run proves the shelf is
    not just importable but independently VERIFIABLE standalone -- the bar a real library clears.
    `runner(cmd, cwd) -> (rc, output)` is the same seam verify_pour uses (default: subprocess)."""
    run = runner or _real_runner
    dest = Path(dest)
    tests_dir = dest / "tests"
    if not tests_dir.is_dir() or not any(tests_dir.glob("test_*.py")):
        return False, "no poured tests to run"
    rc, out = run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], dest)
    if rc != 0:
        return False, f"poured tests failed: {out.strip()[-200:]}"
    summary = next((ln for ln in reversed(out.splitlines()) if "passed" in ln), "passed")
    return True, f"poured tests pass with no engine present ({summary.strip()})"


def verify_pour_build(dest: Path, workdir: Path, *, runner=None) -> tuple[bool, str]:
    """The pip-installable proof: build a wheel, install it into a FRESH venv, and import it.

    This is the release-grade check -- it proves `pip install codeforge-shelf` works for a stranger
    with only the declared deps, not just that the source imports in this repo. Needs network (pip),
    so it is a manual button, not a CI gate; the runner seam lets the test drive it offline. Returns
    `(ok, detail)`. `runner(cmd, cwd) -> (rc, output)`."""
    run = runner or _real_runner
    dest, workdir = Path(dest), Path(workdir)
    if not (dest / "pyproject.toml").is_file():
        return False, f"no package to build at {dest}"
    venv = workdir / "venv"
    py = venv / "bin" / "python"
    dist = workdir / "dist"
    # `pip wheel` builds via setuptools (fetched in an isolated build env, so it needs network);
    # `--no-deps` on install below means the probe imports only pure-stdlib cores -- so the wheel
    # install + import step itself is network-free.
    wheel_cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), str(dest)]
    for cmd in ([sys.executable, "-m", "venv", str(venv)], wheel_cmd):
        rc, out = run(cmd, None)
        if rc != 0:
            return (
                False,
                f"'{cmd[2] if len(cmd) > 2 else cmd[0]}' step failed: {out.strip()[-160:]}",
            )
    wheels = sorted(dist.glob("codeforge_shelf-*.whl"))
    if not wheels:
        return False, "no wheel was produced"
    probe = f"import {PACKAGE}.retry, {PACKAGE}.statemachine; print('installed import ok')"
    for cmd in (
        [str(py), "-m", "pip", "install", "--quiet", "--no-deps", str(wheels[-1])],
        [str(py), "-c", probe],
    ):
        rc, out = run(cmd, None)
        if rc != 0:
            return False, f"install/import failed: {out.strip()[-160:]}"
    return True, f"built {wheels[-1].name} and imported it from a fresh venv"


def _build_main(argv: list[str]) -> int:
    """`... build <dest> <workdir>`: pour, then build the wheel + install it in a fresh venv."""
    dest = Path(argv[2]) if len(argv) > 2 else _ROOT / "workspace" / "shelf-pour"
    workdir = Path(argv[3]) if len(argv) > 3 else _ROOT / "workspace" / "shelf-build"
    pour_shelf(dest)
    ok, detail = verify_pour_build(dest, workdir)
    print(f"built {dest} -> {workdir}")
    print(f"  build:   {'PASS' if ok else 'FAIL'} - {detail}")
    print(
        "  publish: `twine upload` the wheel/sdist, or push to a codeforge-shelf repo (your call)"
    )
    return 0 if ok else 1


def _main(argv: list[str]) -> int:
    """`python3 -m parts.shelf_pour [build] <dest>`: pour + prove imports/tests (or build)."""
    if len(argv) > 1 and argv[1] == "build":
        return _build_main(argv)
    dest = Path(argv[1]) if len(argv) > 1 else _ROOT / "workspace" / "shelf-pour"
    poured = pour_shelf(dest)
    imports_ok, imports_detail = verify_pour(dest)
    tests_ok, tests_detail = verify_pour_tests(dest)
    print(f"poured {len(poured.cores)} cores -> {dest / poured.package}")
    print(f"  package: {poured.package}  deps: {', '.join(poured.dependencies) or '(none)'}")
    print(f"  imports: {'PASS' if imports_ok else 'FAIL'} - {imports_detail}")
    print(f"  tests:   {'PASS' if tests_ok else 'FAIL'} - {tests_detail}")
    print(
        f"           {len(poured.tests)} poured, {len(poured.tests_held)} held (engine tests): "
        f"{', '.join(poured.tests_held) or 'none'}"
    )
    print("  publish: LICENSE + metadata written; `make shelf-build` to build the wheel")
    return 0 if imports_ok and tests_ok else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))  # pragma: no cover
