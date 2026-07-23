"""Correspondence test for the C4 model view (docs/architecture_c4.md).

A diagram that names modules is a claim about the code. VeritasGate for the map: every
module the C4 diagram cites must exist on disk, so a rename that forgets the map turns the
suite red instead of leaving a stale lie on the page. Acceptance (the shipped map is
honest) and refusal (a bogus citation is caught) are both pinned.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DOC = _ROOT / "docs" / "architecture_c4.md"

# Match only real code paths the map should own: the root tick and any parts/ module, including
# one subpackage level (parts/world/, parts/shelf/). (A mention like
# `tests/test_architecture_c4.py` is intentionally NOT matched.)
_MODULE_RE = re.compile(r"\b(forge\.py|parts/(?:[a-z_][a-z0-9_]*/)?[a-z_][a-z0-9_]*\.py)\b")


def _cited_modules(text: str) -> list[str]:
    return sorted(set(_MODULE_RE.findall(text)))


def _missing(text: str, root: Path) -> list[str]:
    return [m for m in _cited_modules(text) if not (root / m).exists()]


def test_the_c4_view_has_both_zoom_levels() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert text.count("```mermaid") >= 2, "expected a Context AND a Container diagram"
    assert "System Context" in text
    assert "Containers" in text


def test_every_module_the_diagram_names_exists() -> None:
    text = _DOC.read_text(encoding="utf-8")
    cited = _cited_modules(text)
    assert len(cited) >= 8, f"map cites too few modules to be a real container view: {cited}"
    assert _missing(text, _ROOT) == [], "C4 map cites a module that does not exist"


def test_the_checker_flags_a_bogus_citation() -> None:
    # Refusal: a diagram that names a non-existent module must be caught, not passed.
    bogus = "container[`parts/does_not_exist.py`]"
    assert _missing(bogus, _ROOT) == ["parts/does_not_exist.py"]
