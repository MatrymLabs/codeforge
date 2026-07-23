"""CARD: forge_line -- run a built part through every manufacturing station, a verdict per stop.

The connective tissue the product vision called its heart. Most manufacturing stations already exist
as parts (search, blueprint, assemble, test, diagnose, document, catalog, file); forge_line is the
CONVEYOR that runs them end to end for a single part and reports a verdict at each stop. It is a
conveyor, not a new machine: it imports and CALLS the existing stations in order, read-and-verify
only. It never mutates the catalog or the registry, never shells a subprocess, and writes to disk
only through an injected Writer seam, so the whole line is deterministic and offline under test.

Two directions. `run_line(part_id)` inspects a BUILT part (ASSEMBLE is a dry-run). `forge_new(name)`
runs the line the other way to START a new part: it validates a blueprint, then GENERATES a scaffold
into the Foundry's git-ignored sandbox (workspace/, never parts/ or main), and stops honestly at a
scaffold -- TEST/DOCUMENT/CATALOG WATCH: the part is not yet implemented, manifested, or filed.
Promotion into parts/ stays a human branch -> check -> PR step.

Run: `python -m parts.forge_line [part_id]` (default token-bucket).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parts import (
    blueprint,
    clone_scan,
    complexity,
    foundry,
    hardware,
    manifest,
    qualitygate,
    registry,
    store_index,
)
from parts.shelf.reporting import write_report
from parts.verdicts import FAIL, NA, PASS, WATCH

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PART = "token-bucket"
_STATION_ORDER = ("BLUEPRINT", "ASSEMBLE", "TEST", "DIAGNOSE", "DOCUMENT", "CATALOG+FILE")

# (category, text) -> the filed path. The ONLY disk-writing seam; tests inject a fake.
Writer = Callable[[str, str], Path]


@dataclass(frozen=True)
class StationReport:
    """One manufacturing stop's verdict and the one-line detail behind it."""

    station: str
    verdict: str  # pass | watch | fail | na
    detail: str


@dataclass
class LineRun:
    """One full run of the line for a part: a verdict per station, the roll-up, the report."""

    part_id: str
    stamp: str
    stations: list[StationReport]
    verdict: str
    report: str = ""


def _catalog(root: Path | None) -> Path | None:
    return None if root is None else root / "catalog" / "parts.yaml"


def _registry_dir(root: Path | None) -> Path | None:
    return None if root is None else root / "registry" / "designations"


def _search(part_id: str, part: hardware.Part | None, root: Path | None) -> StationReport:
    """SEARCH/intake (folds the Idea step): the operator names a need; the line finds the part."""
    if part is None:
        return StationReport("SEARCH", FAIL, f"no part '{part_id}' in the catalog")
    hits = store_index.search(hardware.load_catalog(_catalog(root)), part_id)
    by_need = "yes" if any(p.id == part.id for p in hits) else "no"
    return StationReport(
        "SEARCH",
        PASS,
        f"found {part.name} [{part.id}], reuse_score={part.reuse_score}, by-need={by_need}",
    )


def _validate_blueprint_plan(plan: dict[str, object]) -> StationReport:
    """BLUEPRINT: validate an assembled plan (built + checked in-memory, never written)."""
    try:
        bp = blueprint.from_dict(plan)
        blueprint.to_markdown(bp)  # prove it renders
    except blueprint.BlueprintError as exc:
        return StationReport("BLUEPRINT", FAIL, f"blueprint invalid: {exc}")
    return StationReport(
        "BLUEPRINT", PASS, f"validated: {len(bp.requirements)} requirements, security stated"
    )


def _blueprint(
    part_id: str, part: hardware.Part, man: manifest.PartManifest | None
) -> StationReport:
    """BLUEPRINT for a built part: assemble a plan from the part + manifest, then validate it."""
    return _validate_blueprint_plan(
        {
            "blueprint_id": part_id.replace("-", "_"),
            "title": part.name,
            "intent": part.purpose.strip() or f"reuse the {part.name} part",
            "requirements": list(part.reuse.values()) or list(part.tags) or [part.category],
            "security": [man.security]
            if (man and man.security)
            else [f"provenance: {part.source_status}"],
        }
    )


def _assemble(part: hardware.Part, source_text: str) -> StationReport:
    """ASSEMBLE (dry-run, the part exists): the generator is reachable and the artifact parses."""
    foundry.scaffold_part(part.id)  # prove the generate station is reachable (pure string, no disk)
    try:
        compile(source_text, part.source, "exec")
    except SyntaxError as exc:
        return StationReport("ASSEMBLE", FAIL, f"live source does not parse: {exc}")
    return StationReport(
        "ASSEMBLE",
        PASS,
        f"already forged: scaffold reachable, source parses ({source_text.count(chr(10)) + 1} ln)",
    )


def _test(part: hardware.Part, root: Path | None) -> StationReport:
    """TEST: run the QualityGate on the part's filed designation."""
    records = registry.load_collective(_registry_dir(root))
    record = next((r for r in records if r.file == part.source), None)
    if record is None:
        return StationReport("TEST", NA, f"no filed designation cites {part.source}")
    result = qualitygate.run_gate(record, root=root)
    return StationReport("TEST", result.verdict, f"QualityGate={result.verdict}")


def _diagnose_source(source_text: str, label: str) -> StationReport:
    """DIAGNOSE: peak cyclomatic complexity + a structural-clone scan of one source."""
    try:
        functions = complexity.scan_source(source_text)
        clones = clone_scan.find_clones({label: source_text})
    except (complexity.ComplexityError, clone_scan.CloneError) as exc:
        return StationReport("DIAGNOSE", WATCH, f"diagnosis skipped: {exc}")
    if not functions:
        return StationReport("DIAGNOSE", PASS, "no functions to score, 0 clones")
    peak = max(functions, key=lambda f: f.complexity)
    clone_note = f"{len(clones)} clone group(s)" if clones else "0 clones"
    verdict = WATCH if peak.complexity >= 10 else PASS
    return StationReport(
        "DIAGNOSE", verdict, f"peak McCabe {peak.complexity} in {peak.name}, {clone_note}"
    )


def _diagnose(part: hardware.Part, source_text: str) -> StationReport:
    """DIAGNOSE an existing part's own source."""
    return _diagnose_source(source_text, part.source)


def _document(part_id: str, man: manifest.PartManifest | None, emit: Writer) -> StationReport:
    """DOCUMENT: render the part's manifest and file it through the Writer seam."""
    if man is None:
        return StationReport("DOCUMENT", WATCH, f"no part manifest for {part_id}")
    try:
        markdown = manifest.to_markdown(man)
    except Exception as exc:  # noqa: BLE001 -- manifest render drags in the whole registry; degrade, never crash
        return StationReport("DOCUMENT", WATCH, f"manifest render degraded: {exc}")
    path = emit("manufacture", markdown)
    return StationReport("DOCUMENT", PASS, f"manifest rendered, filed {path.name}")


def _catalog_file(part: hardware.Part, root: Path | None) -> StationReport:
    """CATALOG+FILE (read-and-verify only): the source is present AND filed in the registry."""
    gaps = [
        g
        for g in hardware.source_gaps(root=root, path=_catalog(root))
        if g.startswith(f"{part.id} ")
    ]
    unfiled = part.source in registry.unfiled_modules(root=root)
    if gaps:
        return StationReport("CATALOG+FILE", FAIL, f"broken provenance: {gaps[0]}")
    if unfiled:
        return StationReport(
            "CATALOG+FILE", FAIL, f"module {part.source} is not filed in the registry"
        )
    return StationReport("CATALOG+FILE", PASS, "catalogued + filed, provenance clean")


def _overall(stations: list[StationReport]) -> str:
    """Worst-wins over the content stations: any FAIL -> fail; any WATCH -> watch; else pass."""
    verdicts = {s.verdict for s in stations}
    if FAIL in verdicts:
        return FAIL
    if WATCH in verdicts:
        return WATCH
    return PASS


def run_line(
    part_id: str = _DEFAULT_PART,
    *,
    root: Path | None = None,
    writer: Writer | None = None,
    stamp: str | None = None,
) -> LineRun:
    """Run `part_id` through every manufacturing station in order and return the LineRun.

    Read-and-verify only: no catalog/registry mutation, no subprocess. The single disk-writing seam
    is `writer` (defaults to the dated ReportWriter); inject a fake to keep a test offline."""
    stamp = stamp or date.today().isoformat()
    emit: Writer = writer or (
        lambda category, text: write_report(category, text, root=root, stamp=stamp)
    )

    part = hardware.find_part(part_id, path=_catalog(root))
    content = [_search(part_id, part, root)]
    if part is None:
        content += [
            StationReport(s, NA, "skipped: part not found at SEARCH") for s in _STATION_ORDER
        ]
    else:
        source_text = (root or _ROOT).joinpath(part.source).read_text(encoding="utf-8")
        man = manifest.find_manifest(part_id, root)
        content += [
            _blueprint(part_id, part, man),
            _assemble(part, source_text),
            _test(part, root),
            _diagnose(part, source_text),
            _document(part_id, man, emit),
            _catalog_file(part, root),
        ]

    overall = _overall(content)
    green = sum(1 for s in content if s.verdict == PASS) + (1 if overall == PASS else 0)
    package = StationReport(
        "PACKAGE", overall, f"line complete: {overall}, {green}/8 stations green"
    )
    run = LineRun(part_id=part_id, stamp=stamp, stations=[*content, package], verdict=overall)
    run.report = render_line(run)
    emit("manufacture", run.report)
    return run


def render_line(run: LineRun) -> str:
    """Render a LineRun as the dated station-by-station report (pure: no disk write)."""
    lines = [f"FORGE LINE -- {run.part_id} ({run.stamp})", ""]
    lines += [f"[{s.verdict}] {s.station} -- {s.detail}" for s in run.stations]
    return "\n".join(lines)


def _search_gap(name: str, part: hardware.Part | None, module_exists: bool) -> StationReport:
    """SEARCH for a NEW part: it must be a genuine gap -- nothing already stocked by this name."""
    if module_exists:
        return StationReport("SEARCH", FAIL, f"parts/{name}.py already exists -- not a new part")
    if part is not None:
        return StationReport("SEARCH", FAIL, f"'{part.id}' is already stocked -- not a gap")
    return StationReport("SEARCH", PASS, f"genuine gap: no part named '{name}'")


def _assemble_new(name: str, intent: str, root: Path | None) -> tuple[StationReport, str]:
    """ASSEMBLE a NEW part: generate a scaffold into the git-ignored sandbox (never parts/ or main).

    Real generation, safely: it goes through the Foundry's propose -> approve -> apply guard, which
    writes to workspace/ only, refuses to escape or overwrite, and files evidence."""
    scaffold = foundry.scaffold_part(name)
    try:
        proposal = foundry.propose(
            proposal_id=f"forge_{name}",
            target=f"{name}.py",
            content=scaffold,
            rationale=intent or f"start the {name} part on the manufacturing line",
            affected_part=name,
            test=f"implement {name} and write tests/test_{name}.py",
        )
        path = foundry.apply_proposal(foundry.approve(proposal), root=root)
    except foundry.ProposalError as exc:
        return StationReport("ASSEMBLE", FAIL, f"generation refused: {exc}"), scaffold
    lines = scaffold.count("\n") + 1
    return StationReport(
        "ASSEMBLE", PASS, f"scaffolded to {path.parent.name}/{path.name} ({lines} ln)"
    ), scaffold


def forge_new(
    name: str,
    *,
    intent: str = "",
    root: Path | None = None,
    writer: Writer | None = None,
    stamp: str | None = None,
) -> LineRun:
    """Run the manufacturing line to START a NEW part `name` (lowercase_snake_case).

    The line's other direction: instead of inspecting a built part, it takes a gap, validates a
    blueprint, and GENERATES a scaffold into the Foundry's git-ignored sandbox. It stops honestly at
    a scaffold: TEST/DOCUMENT/CATALOG+FILE WATCH: the part is not yet implemented, manifested,
    or filed. Promotion into parts/ stays a human branch -> check -> PR step. Never writes to parts/
    or the catalog/registry; the sole non-sandbox write (the report) goes through the Writer."""
    stamp = stamp or date.today().isoformat()
    emit: Writer = writer or (
        lambda category, text: write_report(category, text, root=root, stamp=stamp)
    )
    base = root or _ROOT

    part = hardware.find_part(name.replace("_", "-"), path=_catalog(root))
    module_exists = (base / "parts" / f"{name}.py").exists()
    search = _search_gap(name, part, module_exists)
    if search.verdict == FAIL:
        content = [search] + [
            StationReport(s, NA, "skipped: not a new-part gap at SEARCH") for s in _STATION_ORDER
        ]
    else:
        blueprint_report = _validate_blueprint_plan(
            {
                "blueprint_id": name,
                "title": name.replace("_", " ").title(),
                "intent": intent or f"a new part: {name}",
                "requirements": [
                    "one clear job",
                    "explicit inputs and outputs",
                    "a mirrored test twin",
                ],
                "security": [
                    "a sandboxed candidate; promotion into parts/ is a human branch->check->PR"
                ],
            }
        )
        assemble, scaffold = _assemble_new(name, intent, root)
        if assemble.verdict == FAIL:
            # No valid scaffold to test/diagnose/document; the rest skip cleanly.
            content = [search, blueprint_report, assemble] + [
                StationReport(s, NA, "skipped: no scaffold generated")
                for s in ("TEST", "DIAGNOSE", "DOCUMENT", "CATALOG+FILE")
            ]
        else:
            content = [
                search,
                blueprint_report,
                assemble,
                StationReport(
                    "TEST",
                    WATCH,
                    "scaffold parses; the stub raises NotImplementedError, no test twin yet",
                ),
                _diagnose_source(scaffold, f"{name}.py"),
                StationReport(
                    "DOCUMENT", WATCH, f"manifest pending: write docs/hardware/{name}.yaml"
                ),
                StationReport(
                    "CATALOG+FILE",
                    WATCH,
                    "sandbox candidate: not yet catalogued or filed (promotion is a human PR)",
                ),
            ]

    overall = _overall(content)
    green = sum(1 for s in content if s.verdict == PASS) + (1 if overall == PASS else 0)
    outcome = "scaffolded" if search.verdict == PASS else "refused"
    package = StationReport(
        "PACKAGE", overall, f"new part {outcome}: {overall}, {green}/8 stations green"
    )
    run = LineRun(part_id=name, stamp=stamp, stations=[*content, package], verdict=overall)
    run.report = render_line(run)
    emit("manufacture", run.report)
    return run


def line(arg: str = "") -> str:
    """The `line` entry: run the manufacturing line for a part (default token-bucket)."""
    part_id = arg.strip() or _DEFAULT_PART
    return run_line(part_id).report


def forge(arg: str = "") -> str:
    """The `forge` entry: start a NEW part on the line (`forge <lowercase_snake_case_name>`)."""
    name = arg.strip()
    if not name:
        return "forge what? name a new part: forge <lowercase_snake_case_name>"
    return forge_new(name).report


if __name__ == "__main__":
    import sys

    print(line(sys.argv[1] if len(sys.argv) > 1 else ""))
