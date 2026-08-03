"""Cross-repo proof: the engine's workspace GMCP payloads, parsed by the Master Client's parsers.

The engine (`kernel/seedlab/workspace_gmcp.py`) emits the Native Seed workspace packages; the client
(`codeforge-client`) parses them. This script proves the two halves agree end-to-end by building
each payload here and feeding it through the client's own parser code, catching contract drift a
single-repo test cannot see. It is a MANUAL proof, not a CI gate: CI in either repo is single-repo
and network-free by contract, so this reaches a sibling client checkout by path and skips cleanly
when one is not present.

    python3 scripts/native_seed_contract_proof.py
    CODEFORGE_CLIENT_SRC=/path/to/codeforge-client/src python3 scripts/native_seed_contract_proof.py

Exit 0 when every contract agrees (or the client checkout is absent, so it never breaks a run);
exit 1 on drift.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kernel.gmcp import gmcp_frame
from kernel.seedlab import workspace_gmcp as eng
from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel
from kernel.seedlab.project_model import Provenance, SpecSource, extract_model
from kernel.seedlab.source_connector import SourceRecord
from kernel.seedlab.tool_runner import ToolRunResult

_DEFAULT_CLIENT_SRC = Path(__file__).resolve().parents[2] / "codeforge-client" / "src"


def _load_client(src: Path):
    """Import the client's parser cores from a sibling checkout, or return None when absent."""
    if not (src / "codeforge" / "mudclient" / "core" / "build.py").exists():
        return None
    sys.path.insert(0, str(src))
    from codeforge.mudclient.core import build, model, project, source

    return build, model, project, source


def main() -> int:
    src = Path(os.environ.get("CODEFORGE_CLIENT_SRC", _DEFAULT_CLIENT_SRC))
    client = _load_client(src)
    if client is None:
        print(f"SKIP: no client checkout at {src} (set CODEFORGE_CLIENT_SRC); contract not proven.")
        return 0
    cli_build, cli_model, cli_project, cli_source = client

    clock = iter(f"2026-08-01T00:00:{n:02d}+00:00" for n in range(50))
    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: next(clock))
    record = kernel.create_seed("Job Tracker", "josh", "a tiny tracker", seed_id="seed-jt")
    provenance = Provenance("demo", owner="josh")
    source_record = SourceRecord(
        source_id="demo",
        provenance=provenance,
        root="/home/josh/projects/job-tracker",
        file_count=1,
        branch="main",
        commit="a1b2c3d",
    )
    project_model = extract_model(
        SpecSource(
            {"identity": "job-tracker", "entities": ["Application", "Tag"]},
            Provenance("job-tracker", owner="josh"),
        )
    )
    runs = [
        ToolRunResult("seed-jt", "build", "lint", ["make"], 0, "", 0.1, False, "/srv/w", "t"),
        ToolRunResult("seed-jt", "test", "test", ["make"], 1, "", 0.2, False, "/srv/w", "t"),
    ]

    checks: list[tuple[str, bool, str]] = []

    def record_check(name: str, engine_pkg: str, client_pkg: str, ok: bool, detail: str) -> None:
        agree = engine_pkg == client_pkg
        checks.append((name, ok and agree, f"pkg={engine_pkg} {detail}"))
        if not agree:
            checks.append(
                (f"{name} name", False, f"engine {engine_pkg!r} != client {client_pkg!r}")
            )

    status = eng.project_status(record, branch="main", build="passing", tests={"passed": 42})
    parsed_status = cli_project.parse_project_status(status)
    record_check(
        "Project.Status",
        eng.PROJECT_STATUS_PACKAGE,
        cli_project.PROJECT_STATUS_PACKAGE,
        parsed_status.seed == "Job Tracker" and parsed_status.branch == "main",
        f"seed={parsed_status.seed!r} branch={parsed_status.branch!r}",
    )

    tree = eng.source_tree(source_record, ["src/app.py", "tests/test_app.py"], seed="Job Tracker")
    parsed_tree = cli_source.parse_source_tree(tree)
    record_check(
        "Source.Tree",
        eng.SOURCE_TREE_PACKAGE,
        cli_source.SOURCE_TREE_PACKAGE,
        parsed_tree.repository == "job-tracker" and len(parsed_tree.files) == 2,
        f"repo={parsed_tree.repository!r} files={len(parsed_tree.files)}",
    )

    schema = eng.model_schema(project_model, seed="Job Tracker")
    parsed_schema = cli_model.parse_model_schema(schema)
    record_check(
        "Model.Schema",
        eng.MODEL_SCHEMA_PACKAGE,
        cli_model.MODEL_SCHEMA_PACKAGE,
        [e.name for e in parsed_schema.entities] == ["Application", "Tag"],
        f"entities={[e.name for e in parsed_schema.entities]}",
    )

    report = eng.build_report(runs, seed="Job Tracker")
    parsed_report = cli_build.parse_build_report(report)
    record_check(
        "Build.Report",
        eng.BUILD_REPORT_PACKAGE,
        cli_build.BUILD_REPORT_PACKAGE,
        parsed_report.ok is False
        and [s.status for s in parsed_report.steps] == ["passed", "failed"],
        f"ok={parsed_report.ok} steps={[(s.name, s.status) for s in parsed_report.steps]}",
    )

    # Architecture.Map is newer than the other four packages. Prove it only when the client checkout
    # already carries the parser, so this proof stays green against an older client (the contract is
    # additive, and an old client simply does not consume the new package).
    modules = eng.load_module_designations()[:5]
    arch = eng.architecture_map(modules, seed="Job Tracker")
    try:
        from codeforge.mudclient.core import architecture as cli_arch
    except ImportError:
        checks.append(("Architecture.Map", True, "SKIP: client parser absent (additive contract)"))
    else:
        parsed_arch = cli_arch.parse_architecture_map(arch)
        record_check(
            "Architecture.Map",
            eng.ARCHITECTURE_MAP_PACKAGE,
            cli_arch.ARCHITECTURE_MAP_PACKAGE,
            parsed_arch.module_count == len(modules),
            f"modules={parsed_arch.module_count}",
        )

    # Research.Findings is the newest package (CR-0001). Same additive rule: prove it only when the
    # client checkout already carries the parser, so this proof stays green against an older client.
    findings = [
        {"id": "EXP-05", "verdict": "verified improvement", "source": "rd/labs/algorithms"},
        {"id": "EXP-31", "verdict": "hardware store part"},
    ]
    research = eng.research_findings(findings, seed="Job Tracker")
    try:
        from codeforge.mudclient.core import research as cli_research
    except ImportError:
        checks.append(("Research.Findings", True, "SKIP: client parser absent (additive contract)"))
    else:
        parsed_research = cli_research.parse_research_findings(research)
        record_check(
            "Research.Findings",
            eng.RESEARCH_FINDINGS_PACKAGE,
            cli_research.RESEARCH_FINDINGS_PACKAGE,
            parsed_research.finding_count == len(findings),
            f"findings={parsed_research.finding_count}",
        )

    # Form.Schema is the creation front door (CR-0002): the engine projects the Engineering Form,
    # the client parses it into a FormSchema. Same additive rule - prove it only when the client
    # checkout carries the parser, so this proof stays green against an older client.
    from kernel.seedlab.form import FormDefinition

    form_def = FormDefinition.from_dict(
        {
            "common_question_ids": ["name", "owner", "purpose"],
            "questions": {
                "name": {"prompt": "What is this Seed called?", "kind": "text"},
                "owner": {"prompt": "Who owns it (account)?", "kind": "text"},
                "purpose": {"prompt": "In one line, what is it for?", "kind": "text"},
                "combat": {"prompt": "Combat?", "kind": "bool"},
                "pvp": {
                    "prompt": "PvP?",
                    "kind": "choice",
                    "choices": ["none", "open"],
                    "applies_when": {"combat": True},
                },
            },
            "product_types": {
                "game": {
                    "name": "Game world",
                    "question_ids": ["combat", "pvp"],
                    "domain_modules": ["game"],
                },
            },
        }
    )
    form = eng.form_schema(form_def, seed="Job Tracker")
    try:
        from codeforge.mudclient.core import form as cli_form
    except ImportError:
        checks.append(("Form.Schema", True, "SKIP: client parser absent (additive contract)"))
    else:
        parsed_form = cli_form.parse_form_schema(form)
        active = cli_form.active_questions(parsed_form, "game", {"combat": True})
        active_ids = [q.id for q in active]
        pt_ids = [p.id for p in parsed_form.product_types]
        record_check(
            "Form.Schema",
            eng.FORM_SCHEMA_PACKAGE,
            cli_form.FORM_SCHEMA_PACKAGE,
            pt_ids == ["game"] and "pvp" in active_ids,
            f"product_types={pt_ids} active_pvp={'pvp' in active_ids}",
        )

    # Blueprint.List is the planning surface (CR-0003): the engine projects a Seed's filed
    # Blueprints, the client parses them. Same additive rule - prove it only when the client
    # checkout carries the parser, so this proof stays green against an older client.
    from kernel.blueprint import from_dict as make_blueprint

    blueprints = [
        make_blueprint(
            {
                "blueprint_id": "zone_scheduler",
                "title": "Zone Scheduler",
                "intent": "Reset zones on a cadence.",
                "requirements": ["Deterministic order."],
                "security": ["Authz: owner-only trigger."],
                "status": "validated",
            }
        )
    ]
    blueprint_pkg = eng.blueprint_list(blueprints, seed="Job Tracker")
    try:
        from codeforge.mudclient.core import blueprint as cli_blueprint
    except ImportError:
        checks.append(("Blueprint.List", True, "SKIP: client parser absent (additive contract)"))
    else:
        parsed_bp = cli_blueprint.parse_blueprint_list(blueprint_pkg)
        record_check(
            "Blueprint.List",
            eng.BLUEPRINT_LIST_PACKAGE,
            cli_blueprint.BLUEPRINT_LIST_PACKAGE,
            parsed_bp.blueprint_count == len(blueprints)
            and [b.blueprint_id for b in parsed_bp.blueprints] == ["zone_scheduler"],
            f"blueprints={parsed_bp.blueprint_count}",
        )

    # Deploy.Manifest is the deployment-sizing surface (CR-0004): the engine projects a Seed's
    # compiled BuildManifest, the client parses it. Same additive rule - prove it only when the
    # client checkout carries the parser, so this proof stays green against an older client.
    from kernel.seed_package import compile_manifest

    manifest_pkg = eng.deploy_manifest(
        compile_manifest("Job Tracker", "prototype"), seed="Job Tracker"
    )
    try:
        from codeforge.mudclient.core import deploy as cli_deploy
    except ImportError:
        checks.append(("Deploy.Manifest", True, "SKIP: client parser absent (additive contract)"))
    else:
        parsed_deploy = cli_deploy.parse_deploy_manifest(manifest_pkg)
        record_check(
            "Deploy.Manifest",
            eng.DEPLOY_MANIFEST_PACKAGE,
            cli_deploy.DEPLOY_MANIFEST_PACKAGE,
            parsed_deploy.tier_id == "prototype" and parsed_deploy.sizing.target_players == 500,
            f"tier={parsed_deploy.tier_id} players={parsed_deploy.sizing.target_players}",
        )

    for pkg, payload in eng.workspace_packages(
        record,
        source=source_record,
        files=["src/app.py"],
        model=project_model,
        runs=runs,
        modules=modules,
        findings=findings,
    ):
        frame = gmcp_frame(pkg, payload)
        checks.append(
            (
                f"gmcp_frame({pkg})",
                isinstance(frame, bytes) and pkg.encode() in frame,
                f"{len(frame)} B",
            )
        )

    print("\n=== NATIVE SEED WORKSPACE CONTRACT PROOF (engine emit -> client parse) ===\n")
    all_ok = True
    for name, ok, detail in checks:
        all_ok = all_ok and ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:26s} {detail}")
    print(f"\n  VERDICT: {'ALL CONTRACTS AGREE' if all_ok else 'CONTRACT DRIFT DETECTED'}\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
