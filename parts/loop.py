"""CARD: loop -- trace a part through every manufacturing stage and file the evidence.

The connected manufacturing spine. Given a part_id, the loop runner walks through each
stage of the manufacturing loop -- manifest, catalog, blueprint, registry, assembly,
tests, documentation, evidence -- and reports what passed, failed, or was skipped.

This is Phase 11 (Full Engineering Loop) sliced to one part: the proof that the spine
connects end-to-end. Run it from the Workshop (`loop trace <part-id>`) or the CLI
(`python -m parts.loop trace <part-id>`).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class StageResult:
    """One stage's outcome: pass, fail, or skip with a reason."""

    stage: str
    status: str  # pass | fail | skip
    detail: str


@dataclass(frozen=True)
class TraceReport:
    """The full loop trace for one part: every stage result and a verdict."""

    part_id: str
    stamp: str
    stages: tuple[StageResult, ...]
    verdict: str  # pass | fail
    report_path: str


def _stage_manifest(part_id: str, root: Path) -> tuple[StageResult, object]:
    """Stage 1: load and validate the part manifest."""
    from parts.manifest import ManifestError, find_manifest

    try:
        manifest = find_manifest(part_id, root=root)
    except ManifestError as exc:
        return StageResult("manifest", "fail", f"malformed: {exc}"), None
    if manifest is None:
        return StageResult("manifest", "fail", f"no manifest for '{part_id}'"), None
    return StageResult("manifest", "pass", f"{manifest.name} v{manifest.version}"), manifest


def _stage_catalog(part_id: str, root: Path) -> StageResult:
    """Stage 2: verify the part is stocked in the Hardware Store."""
    from parts.hardware import find_part

    catalog_path = root / "catalog" / "parts.yaml"
    part = find_part(part_id, path=catalog_path)
    if part is None:
        return StageResult("catalog", "fail", f"'{part_id}' not in the Hardware Store")
    return StageResult("catalog", "pass", f"stocked as [{part.id}] ({part.maturity})")


def _stage_blueprint(part_id: str, root: Path) -> StageResult:
    """Stage 3: check if a Blueprint exists for this part."""
    from parts.blueprint import load_all

    blueprints = load_all(root=root)
    # blueprint_id uses underscores, part_id uses dashes
    normalized = part_id.replace("-", "_")
    matched = [b for b in blueprints if b.blueprint_id == normalized]
    if not matched:
        return StageResult("blueprint", "skip", "no blueprint filed (not required)")
    bp = matched[0]
    return StageResult("blueprint", "pass", f"'{bp.blueprint_id}' [{bp.status}]")


def _stage_registry(part_id: str, root: Path, manifest: object) -> StageResult:
    """Stage 4: check if the part has a filed designation in the registry."""
    from parts.manifest import PartManifest
    from parts.registry import load_collective

    registry_dir = root / "registry" / "designations"
    collective = load_collective(registry_dir)
    # match by the manifest's source field (authoritative), falling back to part_id
    source_file = (
        manifest.source
        if isinstance(manifest, PartManifest)
        else f"parts/{part_id.replace('-', '_')}.py"
    )
    matched = [d for d in collective if getattr(d, "file", "") == source_file]
    if not matched:
        return StageResult("registry", "fail", f"no designation for {source_file}")
    desig = matched[0]
    return StageResult("registry", "pass", f"{desig.designation} ({desig.status})")


def _stage_assembly(manifest: object, root: Path) -> tuple[StageResult, object]:
    """Stage 5: discover dependencies and compose the assembly."""
    from parts.assembly import AssemblyError, assemble
    from parts.manifest import PartManifest

    if not isinstance(manifest, PartManifest):
        return StageResult("assembly", "skip", "no manifest to assemble from"), None
    try:
        asm = assemble(manifest, root=root)
    except AssemblyError as exc:
        return StageResult("assembly", "fail", str(exc)), None
    summary = (
        f"{len(asm.source_files)} sources, {len(asm.discovered_imports)} imports, "
        f"{len(asm.resolved_parts)} catalog parts"
    )
    return StageResult("assembly", "pass", summary), asm


def _stage_tests(manifest: object, root: Path) -> StageResult:
    """Stage 6: verify test files exist and are non-empty."""
    from parts.manifest import PartManifest

    if not isinstance(manifest, PartManifest):
        return StageResult("tests", "skip", "no manifest")
    if not manifest.tests:
        return StageResult("tests", "fail", "no test files declared in manifest")
    missing = [t for t in manifest.tests if not (root / t).exists()]
    if missing:
        return StageResult("tests", "fail", f"missing: {', '.join(missing)}")
    empty = [t for t in manifest.tests if (root / t).stat().st_size == 0]
    if empty:
        return StageResult("tests", "fail", f"empty: {', '.join(empty)}")
    return StageResult("tests", "pass", f"{len(manifest.tests)} test file(s) present")


def _stage_docs(part_id: str, root: Path) -> StageResult:
    """Stage 7: check for the part's documentation."""
    hw_dir = root / "docs" / "hardware"
    # try the part_id as-is and with underscores (both conventions exist)
    candidates = {part_id, part_id.replace("_", "-"), part_id.replace("-", "_")}
    has_md = any((hw_dir / f"{c}.md").exists() for c in candidates)
    has_yaml = any((hw_dir / f"{c}.yaml").exists() for c in candidates)
    if has_md and has_yaml:
        return StageResult("docs", "pass", "Markdown + YAML manifest present")
    if has_md:
        return StageResult("docs", "pass", "Markdown documentation present")
    if has_yaml:
        return StageResult("docs", "pass", "YAML manifest present")
    return StageResult("docs", "fail", "no documentation found")


def trace(part_id: str, root: Path | None = None, stamp: str | None = None) -> TraceReport:
    """Trace one part through every manufacturing stage and file the evidence report."""
    from parts.assembly import file_evidence
    from parts.reporting import write_report

    base = root or _ROOT
    tag = stamp or date.today().isoformat()
    stages: list[StageResult] = []

    # Stage 1: Manifest
    result, manifest = _stage_manifest(part_id, base)
    stages.append(result)

    # Stage 2: Catalog
    stages.append(_stage_catalog(part_id, base))

    # Stage 3: Blueprint
    stages.append(_stage_blueprint(part_id, base))

    # Stage 4: Registry
    stages.append(_stage_registry(part_id, base, manifest))

    # Stage 5: Assembly
    asm_result, assembly = _stage_assembly(manifest, base)
    stages.append(asm_result)

    # Stage 6: Tests
    stages.append(_stage_tests(manifest, base))

    # Stage 7: Documentation
    stages.append(_stage_docs(part_id, base))

    # File assembly evidence if we got one
    from parts.assembly import Assembly

    if isinstance(assembly, Assembly):
        file_evidence(assembly, root=base)

    # Verdict: pass if no failures
    failures = [s for s in stages if s.status == "fail"]
    verdict = "fail" if failures else "pass"

    # File the loop trace report
    report_text = render_trace_text(part_id, tag, tuple(stages), verdict)
    report = write_report("loop", report_text, root=base, stamp=tag, slug=part_id)

    return TraceReport(
        part_id=part_id,
        stamp=tag,
        stages=tuple(stages),
        verdict=verdict,
        report_path=str(report),
    )


def render_trace_text(
    part_id: str, stamp: str, stages: tuple[StageResult, ...], verdict: str
) -> str:
    """Human-readable rendering of a loop trace."""
    lines = [
        f"MANUFACTURING LOOP TRACE: {part_id}",
        f"Date: {stamp}",
        "",
    ]
    for s in stages:
        icon = {"pass": "[PASS]", "fail": "[FAIL]", "skip": "[SKIP]"}[s.status]
        lines.append(f"  {icon} {s.stage:12} {s.detail}")
    lines.append("")
    lines.append(f"VERDICT: {verdict.upper()}")
    if verdict == "fail":
        failures = [s for s in stages if s.status == "fail"]
        lines.append(f"  {len(failures)} stage(s) failed -- see details above")
    lines.append("")
    return "\n".join(lines)


def render_trace(report: TraceReport) -> str:
    """Render a TraceReport to text."""
    return render_trace_text(report.part_id, report.stamp, report.stages, report.verdict)


# --- CLI entry point ---------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m parts.loop trace <part-id>"""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2 or args[0] != "trace":
        print("Usage: python -m parts.loop trace <part-id>")
        print("  Trace a part through every manufacturing stage.")
        return 1
    part_id = args[1]
    report = trace(part_id)
    print(render_trace(report))
    return 0 if report.verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
