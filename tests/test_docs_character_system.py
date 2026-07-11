"""Correspondence test for docs/character_system.md.

VeritasGate for the guide: it must document every job-schema field and every score display
mode. A new field or mode without a matching doc entry turns the suite red instead of leaving
the guide quietly incomplete.
"""

from __future__ import annotations

from pathlib import Path

from parts.score_sheet import _MODES
from parts.seed import Job

_DOC = (Path(__file__).resolve().parent.parent / "docs" / "character_system.md").read_text(
    encoding="utf-8"
)


def test_the_guide_documents_every_job_schema_field() -> None:
    for field in Job.__annotations__:
        assert f"`{field}`" in _DOC, f"job field {field!r} is not documented in character_system.md"


def test_the_guide_lists_every_score_display_mode() -> None:
    for mode in _MODES:
        assert f"score {mode}" in _DOC or (mode == "standard" and "`score`" in _DOC), mode


def test_the_guide_names_the_character_commands() -> None:
    for command in ("job ", "subjob ", "equip ", "unequip ", "repair", "scan ", "deploy"):
        assert f"`{command}" in _DOC, f"command {command!r} is not documented"
