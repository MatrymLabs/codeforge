"""CARD: assembly -- discover what parts compose a product and file the evidence.

An Assembly records which parts were used to build a product, at what versions, with
what dependencies, and files dated evidence via parts/reporting. It discovers internal
dependencies by walking the source's AST (stdlib ast, no third-party tools) and cross-
references them against the Hardware Store catalog.

Limitation (honest): static imports only. A dynamic importlib.import_module call is
invisible to the AST walk. This is acceptable: every current part uses static imports.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parts.hardware import Part, load_catalog
from parts.manifest import PartManifest
from parts.reporting import write_report

_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Assembly:
    """The record of what composed a product: parts, sources, tests, evidence."""

    assembly_id: str
    part_id: str
    manifest: PartManifest
    discovered_imports: tuple[str, ...]
    resolved_parts: tuple[str, ...]
    source_files: tuple[str, ...]
    test_files: tuple[str, ...]
    stamp: str


class AssemblyError(ValueError):
    """An assembly is invalid -- fail loud, never file a broken record."""


def discover_imports(source_path: Path) -> list[str]:
    """Walk the AST of a Python file and return all `parts.*` imports (sorted, deduped).

    Returns module names like 'parts.statemachine', not file paths.
    """
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, SyntaxError) as exc:
        raise AssemblyError(f"cannot parse {source_path}: {exc}") from exc

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("parts."):
                    modules.add(alias.name.split(".")[0] + "." + alias.name.split(".")[1])
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("parts."):
            parts = node.module.split(".")
            modules.add(parts[0] + "." + parts[1])
    return sorted(modules)


def resolve_parts(imports: list[str], catalog: list[Part]) -> list[str]:
    """Map discovered imports to catalog part_ids.

    An import like 'parts.statemachine' maps to the catalog entry whose source is
    'parts/statemachine.py'. Returns sorted, deduped part_ids.
    """
    source_to_id: dict[str, str] = {}
    for part in catalog:
        source_to_id[part.source] = part.id
    matched: set[str] = set()
    for imp in imports:
        # parts.statemachine -> parts/statemachine.py
        file_path = imp.replace(".", "/") + ".py"
        if file_path in source_to_id:
            matched.add(source_to_id[file_path])
    return sorted(matched)


def assemble(manifest: PartManifest, root: Path | None = None) -> Assembly:
    """Build an Assembly from a manifest: discover imports, resolve parts, verify files."""
    base = root or _ROOT
    stamp = date.today().isoformat()

    # verify source file exists
    source_path = base / manifest.source
    if not source_path.exists():
        raise AssemblyError(f"source file missing: {manifest.source}")

    # discover imports from the main source + all adapters
    all_sources = [manifest.source] + list(manifest.adapters)
    all_imports: set[str] = set()
    source_files: list[str] = []
    for src in all_sources:
        src_path = base / src
        if not src_path.exists():
            raise AssemblyError(f"source/adapter file missing: {src}")
        source_files.append(src)
        all_imports.update(discover_imports(src_path))

    # verify test files exist
    test_files: list[str] = []
    for test in manifest.tests:
        test_path = base / test
        if not test_path.exists():
            raise AssemblyError(f"test file missing: {test}")
        test_files.append(test)

    # resolve imports against catalog
    catalog = load_catalog(base / "catalog" / "parts.yaml")
    resolved = resolve_parts(sorted(all_imports), catalog)

    assembly_id = f"assembly-{manifest.part_id}-{stamp}"

    return Assembly(
        assembly_id=assembly_id,
        part_id=manifest.part_id,
        manifest=manifest,
        discovered_imports=tuple(sorted(all_imports)),
        resolved_parts=tuple(resolved),
        source_files=tuple(source_files),
        test_files=tuple(test_files),
        stamp=stamp,
    )


def render_assembly(asm: Assembly) -> str:
    """Human-readable text rendering of an assembly record."""
    lines = [
        f"ASSEMBLY: {asm.assembly_id}",
        f"Part: {asm.manifest.name} ({asm.manifest.part_id} v{asm.manifest.version})",
        f"Maturity: {asm.manifest.maturity}",
        f"Domain: {asm.manifest.domain}",
        "",
        "Source files:",
    ]
    for src in asm.source_files:
        lines.append(f"  - {src}")
    lines.append("")
    lines.append("Discovered internal imports:")
    for imp in asm.discovered_imports:
        lines.append(f"  - {imp}")
    lines.append("")
    lines.append("Resolved catalog parts:")
    if asm.resolved_parts:
        for pid in asm.resolved_parts:
            lines.append(f"  - {pid}")
    else:
        lines.append("  (none matched in catalog)")
    lines.append("")
    lines.append("Test files:")
    for test in asm.test_files:
        lines.append(f"  - {test}")
    lines.append("")
    return "\n".join(lines)


def file_evidence(asm: Assembly, root: Path | None = None) -> Path:
    """File the assembly as a dated report under reports/assembly/."""
    return write_report(
        "assembly",
        render_assembly(asm),
        root=root,
        stamp=asm.stamp,
        slug=asm.part_id,
    )
