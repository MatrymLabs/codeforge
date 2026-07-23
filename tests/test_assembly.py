"""Test twin for parts/assembly.py -- import discovery and assembly evidence."""

import textwrap

import pytest

from parts.assembly import (
    Assembly,
    AssemblyError,
    assemble,
    discover_imports,
    file_evidence,
    resolve_parts,
)
from parts.hardware import Part
from parts.manifest import PartManifest, find_manifest


def test_discover_imports_finds_parts_imports(tmp_path):
    src = tmp_path / "example.py"
    src.write_text(
        textwrap.dedent("""\
        from parts.shelf.statemachine import Fired
        from parts.shelf.workflow import WorkflowEngine
        import os
        import parts.events
    """)
    )
    imports = discover_imports(src)
    assert "parts.shelf.statemachine" in imports
    assert "parts.shelf.workflow" in imports
    assert "parts.events" in imports
    assert "os" not in imports


def test_discover_imports_ignores_non_parts(tmp_path):
    src = tmp_path / "example.py"
    src.write_text("import json\nfrom pathlib import Path\n")
    assert discover_imports(src) == []


def test_resolve_parts_matches_catalog_entries():
    catalog = [
        Part(
            id="state-machine",
            name="SM",
            source="parts/shelf/statemachine.py",
            category="c",
            purpose="p",
            maturity="shipped",
            risk="low",
            reuse={"g": "x"},
        ),
    ]
    imports = ["parts.shelf.statemachine", "parts.unknown"]
    resolved = resolve_parts(imports, catalog)
    assert "state-machine" in resolved
    assert len(resolved) == 1


def test_assemble_workflow_engine_produces_a_valid_assembly():
    """End-to-end on the real workflow engine manifest."""
    manifest = find_manifest("workflow-engine")
    assert manifest is not None
    asm = assemble(manifest)
    assert isinstance(asm, Assembly)
    assert asm.part_id == "workflow-engine"
    assert len(asm.source_files) >= 3  # workflow.py, quest.py, onboarding.py
    assert "parts.shelf.statemachine" in asm.discovered_imports
    assert len(asm.test_files) == 3


def test_assembly_evidence_is_filed(tmp_path):
    """The report lands under reports/assembly/."""
    manifest = find_manifest("workflow-engine")
    assert manifest is not None
    asm = assemble(manifest)
    path = file_evidence(asm, root=tmp_path)
    assert path.exists()
    assert "assembly" in str(path)
    content = path.read_text()
    assert "workflow-engine" in content


def test_missing_source_file_fails_loud():
    manifest = PartManifest(
        part_id="ghost",
        name="Ghost",
        version="0.1",
        maturity="beta",
        purpose="does not exist",
        source="parts/ghost_nonexistent.py",
        domain="test",
    )
    with pytest.raises(AssemblyError, match="missing"):
        assemble(manifest)
