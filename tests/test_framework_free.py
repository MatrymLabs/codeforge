"""Guard test for ADR-0003: CodeForge is framework-free and stays that way.

This enforces the decision instead of trusting it: if anyone reintroduces Evennia, Django,
or Twisted -- by import or by dependency -- CI goes red. Honest lineage notes in prose
(e.g. "the Evennia-era kernel" in a docstring) are allowed; actual imports/deps are not.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# Forbidden as IMPORTS (not as words in comments/docstrings). ADR-0003.
_FORBIDDEN_IMPORT = re.compile(r"^\s*(?:from|import)\s+(evennia|django|twisted)\b", re.MULTILINE)


def _source_files() -> list[Path]:
    files = [_ROOT / "forge.py"]
    files += sorted(_ROOT.glob("parts/**/*.py"))
    files += sorted(_ROOT.glob("scripts/*.py"))
    return [f for f in files if f.is_file()]


def test_no_forbidden_framework_imports_in_source() -> None:
    offenders: list[str] = []
    for path in _source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in _FORBIDDEN_IMPORT.finditer(text):
            line = text[: match.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(_ROOT)}:{line} -> imports {match.group(1)}")
    assert not offenders, "ADR-0003 violated (framework import reintroduced):\n" + "\n".join(
        offenders
    )


def test_no_forbidden_frameworks_in_dependencies() -> None:
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # Only scan the dependency arrays, not the whole file (comments may mention them).
    dep_blocks = re.findall(r"dependencies\s*=\s*\[(.*?)\]", pyproject, re.DOTALL)
    dep_text = " ".join(dep_blocks).lower()
    for banned in ("evennia", "django", "twisted"):
        assert banned not in dep_text, f"ADR-0003 violated: '{banned}' is a dependency"
