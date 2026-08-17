"""CARD: shelf_pour -- pour the Hardware Store shelf as a standalone installable package.

`cast` pours a GAME; this pours the LIBRARY. It vendors the shelf parts under a FRESH top-level
package (`codeforge_shelf`, no `parts` engine anywhere), auto-detects the third-party deps they
actually import, and writes a `pyproject.toml` that declares them. The result is the vision's second
output made concrete: a Software Hardware Store you can pip-install and import with zero CodeForge
engine present. Because the poured package is renamed, `verify_pour` can prove it in a subprocess
that genuinely cannot reach the engine (importing `kernel.shelf` would find the repo;
`codeforge_shelf` can only be the poured copy).

Reads the shelf; writes only inside the destination dir. No engine state is touched.
"""

from __future__ import annotations

import ast
import re
import subprocess  # nosec B404
import sys
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_PKG = "kernel.shelf"
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
    # Vendored Parts are EXCLUDED. codeforge-shelf is published from this engine, and a Part
    # consumed from the Hardware Store is not this engine's to redistribute: pouring it would put
    # PRT-0007's contract into a public package that carries no card for it and claims a provenance
    # it does not have. The engine consumes the Part; it does not resell it.
    from kernel.hardware import VENDORED_CORES  # noqa: PLC0415

    return [
        p
        for p in sorted(shelf_dir.glob("*.py"))
        if p.name != "__init__.py" and p.stem not in VENDORED_CORES
    ]


def _reaches_engine(source: str, where: str) -> bool:
    """True if a source file imports any non-shelf `parts.*` module (an engine reach).

    A shelf core never does (the shelf_boundary gate enforces it), but a core's TEST twin might --
    an integration test that exercises the core against the live engine. Such a twin cannot run in
    the poured, engine-free package, so the pour holds it back rather than ship a dead test."""
    try:
        tree = ast.parse(source, filename=where)
    except SyntaxError as exc:
        raise ShelfPourError(f"cannot parse {where}: {exc}") from exc  # noqa: TRY003
    for node in ast.walk(tree):
        mods: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        elif isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        for m in mods:
            engine_roots = ("parts", "adapters", "content", "kernel")
            is_engine = m in engine_roots or m.startswith(tuple(r + "." for r in engine_roots))
            if is_engine and not (m == "kernel.shelf" or m.startswith("kernel.shelf.")):
                return True
    return False


def _third_party(files: list[Path], *, exclude: Collection[str] = frozenset()) -> list[str]:
    """The third-party top-level packages a set of files import (non-stdlib, non-`parts`, sorted).

    Detected from the AST so the declared deps stay honest as the code changes. `exclude` drops
    packages already declared elsewhere (e.g. runtime deps, when computing the extra TEST deps)."""
    stdlib = set(sys.stdlib_module_names)
    deps: set[str] = set()
    # Import name != PyPI distribution name for some packages; the poured pyproject must declare
    # the PyPI name or install fails (yaml has no PyPI dist; PyYAML provides `import yaml`).
    pypi_name = {"yaml": "pyyaml"}
    for py in files:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:
            raise ShelfPourError(f"cannot parse {py}: {exc}") from exc  # noqa: TRY003
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                # `codeforge_*` are in-tree optional native accelerators (e.g. codeforge_textkernel)
                # imported behind a try/except fallback -- not PyPI packages, so never a poured dep.
                if (
                    name
                    and name not in stdlib
                    and name != "parts"
                    and not name.startswith("codeforge_")
                    and name not in exclude
                ):
                    deps.add(name)
    return sorted(pypi_name.get(d, d) for d in deps)


def shelf_third_party_deps(shelf_dir: Path | None = None) -> list[str]:
    """The third-party packages the shelf cores import (non-stdlib, non-`parts`), sorted + deduped.

    A pour must declare these or the poured package will not import; detected from the AST so the
    list stays honest as cores change (today: fastapi, pydantic, structlog -- from 2 cores)."""
    base = shelf_dir if shelf_dir is not None else _ROOT / "kernel" / "shelf"
    return _third_party(_core_files(base))


def poolable_twins(
    shelf_dir: Path | None = None, tests_dir: Path | None = None
) -> tuple[list[Path], list[str]]:
    """Split the shelf cores' test twins into (poolable paths, held-back core names).

    A twin is poolable if it reaches no engine part (so it runs against the poured package); a twin
    that imports the engine (an integration test) is held back -- named, not dropped silently."""
    shelf = shelf_dir if shelf_dir is not None else _ROOT / "kernel" / "shelf"
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
    """Rebind a core from `kernel.shelf` to the poured package name (`codeforge_shelf`)."""
    return re.sub(rf"\b{re.escape(_SOURCE_PKG)}\b", PACKAGE, source)


_HOMEPAGE = "https://github.com/MatrymLabs/codeforge"

# CI for the published repo: run the poured tests on every push, and publish to PyPI on a GitHub
# Release via Trusted Publishing (OIDC -- no stored token). The `pypi` environment is the deploy
# gate the maintainer configures as the PyPI pending-publisher's environment.
_TEST_WORKFLOW = """\
name: test
# push limited to main: `on: [push, pull_request]` fires BOTH events for a push to a PR
# branch, running every job twice for one commit.
on:
  push:
    branches: [main]
  pull_request:

# Cancel superseded PR runs. Pull requests ONLY: `github.ref != 'refs/heads/main'` is true
# for a release event (its ref is the tag) and could cancel a release mid-publish.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.13"
      - run: python -m pip install --upgrade pip
      - run: python -m pip install .[test,dev]
      - run: ruff format --check .
      - run: ruff check .
      - run: mypy
      - run: pytest -q
"""

_RELEASE_WORKFLOW = """\
name: release
on:
  release:
    types: [published]

# Serialise releases without ever cancelling one: a cancelled publish is worse than a
# queued publish. cancel-in-progress stays false here by omission.
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
permissions:
  contents: read
jobs:
  pypi:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Trusted Publishing (OIDC): no API token stored anywhere
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.13"
      - run: python -m pip install build
      - run: python -m build  # sdist + wheel
      - uses: pypa/gh-action-pypi-publish@release/v1
"""

# The fleet control panel (env - fix - lint - typecheck - test - check), so a codeforge-shelf
# contributor drives the same buttons as every other vessel. Recipe lines are tab-indented.
_MAKEFILE = (
    "# codeforge-shelf control panel (fleet standard). Poured; re-poured, never hand-edited.\n"
    ".PHONY: env fix lint typecheck test check\n"
    "env:  ## venv + editable install with the test/dev extras\n"
    '\tpython3 -m venv .venv && .venv/bin/pip install -e ".[test,dev]"\n'
    "fix:  ## auto-format + lint-fix (mutates)\n"
    "\truff format . && ruff check --fix .\n"
    "lint:  ## format check + lint (report only)\n"
    "\truff format --check . && ruff check .\n"
    "typecheck:  ## mypy over the package\n"
    "\tmypy\n"
    "test:  ## the poured test twins (engine-free)\n"
    "\tpytest -q\n"
    "check: lint typecheck test  ## the full gate\n"
)


#: Fleet gate standard rule 1: pin the tools that decide a verdict. The poured shelf's
#: pyproject is GENERATED, so pinning it by hand was a fix at the output and the next pour
#: silently reverted it (caught by shelf-drift, 2026-08-08). The pin belongs here, at the
#: generator. Runtime deps are deliberately absent: only gate tooling is pinned.
GATE_TOOL_PINS = {
    "hypothesis": "6.165.2",
    "mypy": "2.3.0",
    "pytest": "9.1.1",
    "ruff": "0.16.1",
}


def _pinned(name: str) -> str:
    """Attach the fleet-wide pin to a gate tool; leave every other dependency untouched."""
    version = GATE_TOOL_PINS.get(name)
    return f"{name}=={version}" if version else name


def _pyproject(deps: list[str], test_deps: list[str]) -> str:
    # Heavy runtime deps (from the config + observability parts) are opt-in extras, so the base
    # install is pure stdlib. Tests import every part, so the test group carries the extras too.
    extras_lines = "".join(f'    "{d}",\n' for d in deps)
    test_lines = "".join(f'    "{_pinned(d)}",\n' for d in sorted(set(test_deps) | set(deps)))
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
        'version = "0.3.0"\n'
        'description = "The CodeForge Hardware Store: reusable, engine-agnostic Python parts."\n'
        'readme = "README.md"\n'
        'requires-python = ">=3.12"\n'
        'license = "MIT"\n'
        'license-files = ["LICENSE"]\n'
        'authors = [{ name = "MatrymLabs" }]\n'
        'keywords = ["reusable", "stdlib", "resilience", "patterns", "hardware-store"]\n'
        "classifiers = [\n"
        f"{classifiers}"
        "]\n"
        # The base install is pure stdlib. The few parts that need a framework (config -> pydantic,
        # observability -> structlog/fastapi) declare it in the optional `extras` group, so a
        # consumer who only wants the stdlib parts carries no heavy dependency footprint.
        "dependencies = []\n\n"
        "[project.optional-dependencies]\n"
        "extras = [\n"
        f"{extras_lines}"
        "]\n"
        "test = [\n"
        f"{test_lines}"
        "]\n"
        f'dev = ["{_pinned("ruff")}", "{_pinned("mypy")}"]\n\n'
        "[project.urls]\n"
        f'Homepage = "{_HOMEPAGE}"\n'
        f'Source = "{_HOMEPAGE}"\n\n'
        "[tool.setuptools]\n"
        f'packages = ["{PACKAGE}"]\n\n'
        "[tool.setuptools.package-data]\n"
        f'{PACKAGE} = ["py.typed"]\n\n'  # ship the PEP 561 marker so consumers get the types
        "[tool.pytest.ini_options]\n"
        'markers = ["property: hypothesis-driven property tests"]\n\n'
        # The parts are annotated (PEP 561) and type-clean in CodeForge; ship a mypy config so a
        # codeforge-shelf contributor type-checks identically. Framework stubs vary across versions,
        # so don't gate on third-party stubs (the parts' own types are what matter).
        "[tool.mypy]\n"
        'python_version = "3.12"\n'
        f'files = ["{PACKAGE}"]\n'
        "ignore_missing_imports = true\n\n"
        # The parts are already lint-clean in CodeForge; ship the same config so a codeforge-shelf
        # contributor lints identically. Target 3.12 -- the parts use PEP 695 type-parameter syntax
        # (`class Foo[T]`, 3.12+), which is also the package's true requires-python floor.
        "[tool.ruff]\n"
        "line-length = 100\n"
        'target-version = "py312"\n\n'
        "[tool.ruff.lint]\n"
        'select = ["E", "F", "I", "UP", "B", "SIM"]\n'
    )


def _readme(cores: list[str], deps: list[str], n_tests: int, held: list[str]) -> str:
    listing = "\n".join(f"- `{PACKAGE}.{c}`" for c in cores)
    dep_note = (
        "The base install is **pure stdlib** (no third-party runtime deps). The `config` and "
        f"`observability` parts need the optional extras: `pip install codeforge-shelf[extras]` "
        f"(pulls {', '.join(deps)})."
        if deps
        else "The package is **pure stdlib**: no third-party runtime dependencies."
    )
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
        "Reusable, engine-agnostic Python parts, proven in the CodeForge platform and "
        "poured here as a\n"
        "standalone package. No game engine is required to use them. Fully typed (PEP 561).\n\n"
        "## Install\n\n"
        "```sh\n"
        "pip install codeforge-shelf\n"
        f"# or from source: pip install git+{_HOMEPAGE}-shelf\n"
        "```\n\n"
        f"{dep_note}\n\n"
        "## Usage\n\n"
        f"{usage}\n"
        f"## Parts ({len(cores)})\n\n"
        f"{listing}\n\n"
        "## Tests\n\n"
        f"{n_tests} test twins ship with the package and pass with no engine present "
        "(`pip install .[test] && pytest`).\n"
        f"{held_note}\n"
        "## Provenance\n\n"
        f"Generated from [CodeForge]({_HOMEPAGE}) by its `kernel/shelf_pour.py`,which vendors the\n"
        "engine-agnostic parts of `kernel/shelf/` under a fresh package name and proves they\n"
        "import and test standalone. Re-poured, never hand-edited.\n"
    )


_CHANGELOG = """\
# Changelog

All notable changes to `codeforge-shelf`. This package is generated (poured) from CodeForge; the
version tracks the pour, not hand edits.

## 0.3.0

- Renamed the units from "cores" to **Parts** (the fleet's canonical term for a Hardware Store unit;
  see the ship Engineering Identity). Docs/display only -- no import or API change.
- Moved the heavy runtime dependencies (fastapi, pydantic, structlog) to an optional `extras` group,
  so the **base install is now pure stdlib**. The `config` and `observability` parts need
  `pip install codeforge-shelf[extras]`. Corrects the earlier "stdlib-only" copy (inaccurate).
- Added a Makefile control panel (env/fix/lint/typecheck/test/check) and a mypy typecheck gate to
  CI, bringing the package to fleet-standard parity.

## 0.2.0

- Five more cores poured as the engine's Hardware Store grew (27 -> 32): `affixes`, `completeness`,
  `conditions`, `reward_curve`, and `textmatch` (fuzzy match / Levenshtein). Kept the pour in step
  with the engine; a drift-detection gate now prevents the two from silently diverging again.

## 0.1.0

- Initial release: the CodeForge Hardware Store poured standalone -- reusable, engine-agnostic
  Python cores extracted from the CodeForge platform with a one-way dependency, typed (PEP 561),
  shipping their engine-free test twins (they pass with no engine present).
"""


_AGENTS = """\
# AGENTS.md - codeforge-shelf

The published Hardware Store mirror.

## THIS REPOSITORY IS GENERATED. DO NOT EDIT IT.

Every file here, including this one, is poured from `codeforge` by `kernel/shelf_pour.py`. A
`shelf-drift` gate asserts `mirror == fresh pour of the engine`.

Editing here, **including merging a dependency bump**, breaks that invariant and reddens CI on
every later codeforge PR. That has happened three times: Dependabot PRs merged into this mirror
left it out of sync, and two unrelated README-only changes went red as a result.

**Fix the generator, never the file.** Changes belong in `codeforge/kernel/shelf_pour.py`, after
which `shelf-sync` re-pours this repo automatically.

## Required Reading

The Workshop's doctrine and live board are canonical in the `ship` repository:

- `MATRYM_WORKSHOP_CANON.md` - the single active Workshop doctrine. Nothing else governs
- `.ai/HANDOFF_PROTOCOL.md` - how the two Benches exchange work under it
- `.ai/WORKBENCH.md` - the live operating surface. The Active Build is at the top

This repository carries no synced doctrine block, and that is deliberate rather than an oversight:
a block rendered here would be poured output, so the drift gate would fight the doctrine gate over
the same bytes. Doctrine belongs where the work is dispatched, and no Bench is dispatched here.

If you are working on the Store's CONTENTS, you are working in `codeforge`, and its `AGENTS.md`
applies. Nothing in this repository is edited by hand.

## The gate

```bash
make check
```

Runs the poured cores' own tests. It proves the pour is sound; it does not certify anything.
Certification is R&D's Verdict Gate, in `hardware-store`.
"""


def pour_shelf(dest: Path, *, shelf_dir: Path | None = None) -> PouredShelf:
    """Vendor the shelf into `dest` as the standalone `codeforge_shelf` package.

    Writes `dest/codeforge_shelf/<core>.py` (imports rebound off `parts`), a `pyproject.toml` that
    declares the auto-detected deps, and a README. Returns a PouredShelf record. Writes only under
    `dest`; reads the live shelf read-only."""
    src = shelf_dir if shelf_dir is not None else _ROOT / "kernel" / "shelf"
    tests_src = shelf_dir.parent.parent / "tests" if shelf_dir is not None else _ROOT / "tests"
    cores = _core_files(src)
    if not cores:
        raise ShelfPourError(f"no shelf cores found under {src}")  # noqa: TRY003
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
    # A generated repo still needs to tell an agent it is generated. Poured, not hand-written,
    # so it cannot drift from the rule it states.
    (dest / "AGENTS.md").write_text(_AGENTS, encoding="utf-8")
    (dest / "Makefile").write_text(_MAKEFILE, encoding="utf-8")
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
    # Fixed argv, no shell; used only inside the poured package directory.
    proc = subprocess.run(  # nosec B603  # noqa: PLW1510, S603
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
                f"'{cmd[2] if len(cmd) > 2 else cmd[0]}' step failed: {out.strip()[-160:]}",  # noqa: PLR2004
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
    dest = Path(argv[2]) if len(argv) > 2 else _ROOT / "workspace" / "shelf-pour"  # noqa: PLR2004
    workdir = Path(argv[3]) if len(argv) > 3 else _ROOT / "workspace" / "shelf-build"  # noqa: PLR2004
    pour_shelf(dest)
    ok, detail = verify_pour_build(dest, workdir)
    print(f"built {dest} -> {workdir}")
    print(f"  build:   {'PASS' if ok else 'FAIL'} - {detail}")
    print(
        "  publish: `twine upload` the wheel/sdist, or push to a codeforge-shelf repo (your call)"
    )
    return 0 if ok else 1


def pour_drift(shelf_repo: Path, *, shelf_dir: Path | None = None) -> list[str]:
    """Files where a fresh pour differs from `shelf_repo`: missing there, or content-mismatched.

    Empty list = in sync. One-directional: it checks every file the pour WRITES against the repo, so
    repo-only files (a hand-added .gitignore, local caches) are not drift -- only a stale or
    hand-edited *poured* file is. This is the invariant the drift gate enforces so codeforge and
    codeforge-shelf cannot silently diverge again."""
    tmp = Path(tempfile.mkdtemp(prefix="pour_drift_"))
    pour_shelf(tmp, shelf_dir=shelf_dir)
    drift: list[str] = []
    for poured in sorted(tmp.rglob("*")):
        if not poured.is_file() or "__pycache__" in poured.parts:
            continue
        rel = poured.relative_to(tmp)
        mirror = shelf_repo / rel
        if not mirror.is_file():
            drift.append(f"missing in shelf: {rel}")
        elif poured.read_bytes() != mirror.read_bytes():
            drift.append(f"content drift: {rel}")
    return drift


def _drift_main(argv: list[str]) -> int:
    """`python3 -m kernel.shelf_pour --drift <codeforge-shelf>`: fail if the repo is out of sync."""
    drift = pour_drift(Path(argv[2]))
    if drift:
        print(f"POUR DRIFT: codeforge-shelf is out of sync with the engine ({len(drift)} file(s)):")
        for item in drift:
            print(f"  - {item}")
        print("Fix: re-pour (`python -m kernel.shelf_pour <codeforge-shelf>`), verify, and push.")
        return 1
    print("pour in sync: codeforge-shelf matches a fresh pour of the engine's Hardware Store")
    return 0


def _main(argv: list[str]) -> int:
    """`python3 -m kernel.shelf_pour [build|--drift] <dest>`: pour + prove imports/tests."""
    if len(argv) > 1 and argv[1] == "build":
        return _build_main(argv)
    if len(argv) > 2 and argv[1] == "--drift":  # noqa: PLR2004
        return _drift_main(argv)
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
