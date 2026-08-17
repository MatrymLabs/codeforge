"""CARD: workspace_gmcp -- project an engineering Seed's state into the Master Client's workspace
GMCP contracts, and turn a client's create request into a real Seed.

The Master Client renders four read-only Engineering Workspace views (Project Hub, Source Explorer,
Model view, Build Report) plus a Seed-creation flow, each fed by a named GMCP package. Stages 0-2 of
the Seed Interface Directive taught this engine the `Seed.Hello` handshake (kernel/gmcp.py); this
card teaches it the WORKSPACE half: it reads the seedlab models that already exist and shapes them
into the exact packages the client parses, and it reads a client's `Seed.Create` request and mints a
real Seed through the Kernel.

Two laws hold, the same as kernel/gmcp.py:

- **State is canonical; a report is a read-only projection.** Each builder takes a seedlab record
  (`BlueprintRecord`, `SourceRecord`, `ProjectModel`) and returns a JSON-able dict - never a second
  source of truth, never a mutation. The gateway owns the socket and decides when to send.
- **Honest by construction (No Vision Theater).** A builder emits only what THIS card wires. Per-
  entity fields are not modeled yet, so `Model.Schema` carries entity names with empty field lists.
  `Build.Report` projects the `tool_runner` stage's real runs into build STEPS and an honest `ok`
  verdict, but its `tests`/`artifacts` seams stay empty until a stage actually parses test counts or
  records artifacts - the run model does not carry them, and fabricating a count would be a lie. As
  those land, the packages fill; the contract shape does not change.

The client's parsers are defensive (a missing field takes a default, a bad frame is surfaced), so
the engine emits the subset it has and the client renders it. Pure and offline: the only side effect
is through an injected `BlueprintKernel` (a test injects an in-memory store); nothing touches
a socket.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePath

from kernel.blueprint import Blueprint
from kernel.blueprint import to_dict as blueprint_record
from kernel.seed_package import BuildManifest
from kernel.seedlab.form import _SPEC_SCHEMA as FORM_SPEC_SCHEMA
from kernel.seedlab.form import EngineeringForm, FormDefinition, FormError
from kernel.seedlab.kernel import BlueprintKernel, BlueprintKernelError, BlueprintRecord
from kernel.seedlab.project_model import ProjectModel
from kernel.seedlab.source_connector import SourceRecord, source_connection
from kernel.seedlab.tool_runner import ToolRunResult

# --- the workspace package names (must match the client's core/*.py PACKAGE constants) -----------
#: An engineering Seed's project status -> the client's Project Hub (core/project.py).
PROJECT_STATUS_PACKAGE = "Project.Status"
#: An engineering Seed's source tree -> the client's Source Explorer (core/source.py).
SOURCE_TREE_PACKAGE = "Source.Tree"
#: The structured source connector record -> the client's connector surface.
SOURCE_CONNECTION_PACKAGE = "Source.Connection"
#: An engineering Seed's data model -> the client's Model view (core/model.py).
MODEL_SCHEMA_PACKAGE = "Model.Schema"
#: A client's request to CREATE a Seed (client -> engine); the verdict below is the reply.
SEED_CREATE_PACKAGE = "Seed.Create"
#: The engine's verdict on a create request (engine -> client), read by core/seed_create.py.
SEED_CREATED_PACKAGE = "Seed.Created"
#: An engineering Seed's build/test run -> the client's Build Report (core/build.py).
BUILD_REPORT_PACKAGE = "Build.Report"
#: An engineering Seed's module map -> the client's Architecture Explorer (core/architecture.py).
ARCHITECTURE_MAP_PACKAGE = "Architecture.Map"
#: An engineering Seed's body of research -> the client's Research Explorer (core/research.py).
RESEARCH_FINDINGS_PACKAGE = "Research.Findings"
#: The Engineering Form projected -> the client's Seed Creation Wizard (core/form.py).
FORM_SCHEMA_PACKAGE = "Form.Schema"
#: A client's completed Form answers (client -> engine); the `Seed.Created` verdict is the reply.
FORM_SUBMIT_PACKAGE = "Form.Submit"
#: A client's request to be served a workspace (client -> engine); an optional `{"tier": id}` picks
#: the deployment tier for the reply's `Deploy.Manifest`. Read-only: it triggers a projection, never
#: a mutation.
WORKSPACE_REQUEST_PACKAGE = "Workspace.Request"
#: A Seed's filed Blueprints (planning specs) -> the client's Blueprint Panel (core/blueprint.py).
BLUEPRINT_LIST_PACKAGE = "Blueprint.List"
#: A Seed's deployment-sizing manifest (tier + derived world sizing) -> the client's Deployment
#: Panel (core/deploy.py). Read-only: the honest sizing/hardware read, NOT a live cloud deploy.
DEPLOY_MANIFEST_PACKAGE = "Deploy.Manifest"
#: The running instance's own live status -> the client's instance panel (core/deploy_status).
DEPLOY_STATUS_PACKAGE = "Deploy.Status"

#: The kinds of Seed a client may ask to create (matches the client's SEED_KINDS).
SEED_KINDS = ("engineering", "game")


class WorkspaceContractError(ValueError):
    """A `Seed.Create` request that is not a valid request object -- fail loud, never mint a Seed
    from a malformed or untrusted frame. (The client validated its own input; the engine, which does
    not trust the wire, validates again.)"""


# --- projecting seedlab state into the read-only view contracts ---------------------------------


def project_status(
    record: BlueprintRecord,
    *,
    branch: str | None = None,
    build: str | None = None,
    tests: dict[str, int] | None = None,
) -> dict[str, object]:
    """The `Project.Status` payload for a Seed: its name and lifecycle phase, and (when known) the
    branch it works on, its build status, and its test tally. `phase` is the Kernel's lifecycle
    status (created/running/stopped/archived). `branch`/`build`/`tests` are optional because the
    seedlab stages that source them may not have run - the client defaults what is absent."""
    payload: dict[str, object] = {
        "seed": record.identity.name,
        "phase": record.status,
    }
    if branch:
        payload["branch"] = branch
    if build:
        payload["build"] = {"status": build}
    if tests is not None:
        payload["tests"] = {
            "passed": int(tests.get("passed", 0)),
            "failed": int(tests.get("failed", 0)),
        }
    return payload


def source_tree(source: SourceRecord, files: list[str], *, seed: str) -> dict[str, object]:
    """The `Source.Tree` payload for a registered source: the repository and where it stands
    (branch, commit), and the files it exposes. `repository` is the source root's basename; `files`
    are the connector's approved relative paths (all files, so `kind` is "file"; line counts are
    unknown, so the client marks them). The connector is read-only, so `dirty` is not modeled."""
    repository = PurePath(source.root).name or source.source_id
    entries = [{"path": path, "kind": "file"} for path in files]
    payload: dict[str, object] = {
        "seed": seed,
        "repository": repository,
        "files": entries,
    }
    if source.branch:
        payload["branch"] = source.branch
    if source.commit:
        payload["commit"] = source.commit
    return payload


def source_connection_package(
    source: SourceRecord, *, seed: str | None = None
) -> dict[str, object]:
    """The `Source.Connection` payload for a registered local source connector."""
    payload = source_connection(source)
    if seed is not None:
        payload["seed"] = seed
    return payload


def model_schema(model: ProjectModel, *, seed: str | None = None) -> dict[str, object]:
    """The `Model.Schema` payload for an extracted project model: its entities WITH their fields
    (AP-08: the code-first extractor fills `entity_fields`; a layout-inferred or older model has
    none, and the client renders "Entity (0 fields)" honestly). `seed` labels the project
    (defaults to the model's own identity)."""
    return {
        "seed": seed or model.identity,
        "entities": [
            {"name": name, "fields": list(model.entity_fields.get(name, []))}
            for name in model.entities
        ],
    }


def build_report(
    runs: Sequence[ToolRunResult],
    *,
    seed: str,
    tests: dict[str, int] | None = None,
    artifacts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """The `Build.Report` payload for a Seed's tool runs: each run becomes a build STEP (named by
    its profile, its status the run's outcome), and the report is `ok` only when every step passed
    (an empty run log is not `ok` - nothing ran to succeed).

    `tests`/`artifacts` are optional seams left open on purpose: the run model (`ToolRunResult`)
    records a run's exit, timing, and output but not parsed test COUNTS or emitted artifacts, so
    this builder does not invent them. Absent, the client renders 0 tests and no artifacts, which is
    honest. A later stage that actually sources counts or artifacts passes them here; the contract
    shape does not change (No Vision Theater)."""
    payload: dict[str, object] = {
        "seed": seed,
        "ok": bool(runs) and all(run.ok for run in runs),
        "steps": [_run_step(run) for run in runs],
    }
    if tests is not None:
        payload["tests"] = {
            "passed": int(tests.get("passed", 0)),
            "failed": int(tests.get("failed", 0)),
            "skipped": int(tests.get("skipped", 0)),
        }
    if artifacts:
        payload["artifacts"] = artifacts
    return payload


def _run_step(run: ToolRunResult) -> dict[str, str]:
    """One build step from a tool run: named by its profile (its kind when it has no profile), its
    status the run's outcome - "passed" on a clean exit, "timed out" when it ran over, else
    "failed". The client drops a nameless step, so the name always falls back to a non-empty
    label."""
    if run.timed_out:
        status = "timed out"
    elif run.exit_code == 0:
        status = "passed"
    else:
        status = "failed"
    return {"name": run.profile or run.kind or "run", "status": status}


# --- the module map: the classification registry -> the client's Architecture Explorer ----------

#: The classification registry an engineering Seed's module map projects (the repo's own filing).
_MODULES_REGISTRY = (
    Path(__file__).resolve().parents[2] / "registry" / "designations" / "modules.json"
)

#: The module fields the map projects, in render order. Only these leave the engine (No Vision
#: Theater): the registry carries 19 fields per module, but the map shows the renderable subset.
_MODULE_FIELDS = ("designation", "name", "domain", "function", "file", "status")


def architecture_map(
    modules: Sequence[Mapping[str, object]], *, seed: str | None = None
) -> dict[str, object]:
    """The `Architecture.Map` payload for an engineering Seed: a projection of the classification
    registry (the repo's module filing) into a domain-grouped module map the client's Architecture
    Explorer renders.

    Each module contributes the renderable subset of its registry record (`_MODULE_FIELDS`); a field
    the record lacks is simply absent, never invented. `domains` is the module count per domain,
    sorted, so the client can group without re-counting. `depends_on`/`related` edges are a seam
    left open on purpose (most records carry none today); when the registry fills them, the map can
    carry them, and the shape does not change. Pure and offline: it shapes the list it is given."""
    projected: list[dict[str, object]] = []
    domains: Counter[str] = Counter()
    for module in modules:
        entry = {field: module[field] for field in _MODULE_FIELDS if field in module}
        projected.append(entry)
        domains[str(module.get("domain", "unknown"))] += 1
    projected.sort(key=lambda entry: str(entry.get("designation", "")))
    payload: dict[str, object] = {
        "source": "registry/designations/modules.json",
        "module_count": len(projected),
        "domains": [{"domain": name, "count": n} for name, n in sorted(domains.items())],
        "modules": projected,
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


def load_module_designations(path: Path | str | None = None) -> list[dict[str, object]]:
    """Read the classification registry's module records for `architecture_map`. The default path is
    resolved at CALL time (not import time) so a test can point it at a fixture. A registry that is
    absent or is not a JSON list fails loud (a silently empty map would be a lie)."""
    registry = Path(path) if path is not None else _MODULES_REGISTRY
    data = json.loads(registry.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise BlueprintKernelError(f"module registry {registry} is not a JSON list")
    return [module for module in data if isinstance(module, dict)]


# --- the research surface: the R&D Factory + FGL provenance -> the Research Explorer -------------

#: The finding fields the projection carries, in render order. Only these leave the engine (No
#: Vision Theater): a research record may hold more, but the panel renders the source -> claim ->
#: evidence -> verdict trace. `id` anchors a finding; a field the record lacks is absent, not blank.
_FINDING_FIELDS = ("id", "title", "question", "status", "verdict", "source", "evidence", "summary")


def research_findings(
    findings: Sequence[Mapping[str, object]], *, seed: str | None = None
) -> dict[str, object]:
    """The `Research.Findings` payload for an engineering Seed: a projection of its body of research
    (R&D Factory experiments + FGL provenance) into a verdict-grouped finding list the client's
    Research Explorer renders.

    Each finding contributes the renderable subset of its record (`_FINDING_FIELDS`); a field the
    record lacks is absent, never invented (same law as `architecture_map`). `verdicts` is the
    finding count per Verdict-Gate label, sorted, so the client groups without re-counting (mirrors
    `Architecture.Map.domains`). Findings sort by `id` so the list is stable. The Seed owns its
    verdict vocabulary; the engine does not enumerate it. Pure and offline: it shapes the list it is
    given, never reads research state or assigns a verdict."""
    projected: list[dict[str, object]] = []
    verdicts: Counter[str] = Counter()
    for finding in findings:
        entry = {field: finding[field] for field in _FINDING_FIELDS if field in finding}
        projected.append(entry)
        verdict = finding.get("verdict")
        if isinstance(verdict, str) and verdict.strip():
            verdicts[verdict] += 1
    projected.sort(key=lambda entry: str(entry.get("id", "")))
    payload: dict[str, object] = {
        "finding_count": len(projected),
        "verdicts": [{"verdict": name, "count": n} for name, n in sorted(verdicts.items())],
        "findings": projected,
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


def load_research_findings(path: Path | str) -> list[dict[str, object]]:
    """Read a Seed's research manifest (a JSON list of finding records) for `research_findings`.

    Unlike the repo-global module registry, a research surface is per-Seed, so the path is explicit:
    a Seed points at its own manifest (e.g. an R&D Factory export). A manifest that is not a JSON
    list fails loud (a silently empty research surface would be a lie); a stray non-dict entry is
    skipped. The read is call-time so a test can point it at a fixture."""
    manifest = Path(path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise BlueprintKernelError(f"research manifest {manifest} is not a JSON list")
    return [finding for finding in data if isinstance(finding, dict)]


# --- the create round-trip: a client request becomes a real Seed --------------------------------


@dataclass(frozen=True)
class SeedCreateRequest:
    """A validated `Seed.Create` request from a client: the `name` to mint, its `kind`, and an
    optional `description`. The engine does not trust the wire, so this is the checked shape a raw
    frame is parsed into before the Kernel ever sees it."""

    name: str
    kind: str
    description: str = ""


def parse_seed_create(data: object) -> SeedCreateRequest:
    """Parse an untrusted `Seed.Create` frame into a validated request, or fail loud
    (`WorkspaceContractError`).

    The frame must be an object naming a non-empty `name` and a known `kind`; `description` is
    optional. The engine re-validates what the client already checked - defense in depth: a
    malformed or hostile frame never reaches the Kernel."""
    if not isinstance(data, dict):
        raise WorkspaceContractError("Seed.Create: payload must be an object")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise WorkspaceContractError("Seed.Create: 'name' must be a non-empty string")
    kind = data.get("kind")
    if not isinstance(kind, str) or kind.strip().lower() not in SEED_KINDS:
        raise WorkspaceContractError(f"Seed.Create: 'kind' must be one of {', '.join(SEED_KINDS)}")
    description = data.get("description")
    description = description.strip() if isinstance(description, str) else ""
    return SeedCreateRequest(name=name.strip(), kind=kind.strip().lower(), description=description)


def seed_created(name: str, ok: bool, *, seed_id: str = "", reason: str = "") -> dict[str, object]:
    """The `Seed.Created` verdict payload: the `name` the request concerned, whether it was `ok`,
    and a detail (the new Seed's `id` on success, the `reason` on refusal). The client reads this as
    an untrusted verdict, shaped exactly as core/seed_create.parse_seed_created expects."""
    payload: dict[str, object] = {"name": name, "ok": ok}
    if ok and seed_id:
        payload["id"] = seed_id
    if not ok and reason:
        payload["reason"] = reason
    return payload


def create_from_request(kernel: BlueprintKernel, data: object, *, owner: str) -> dict[str, object]:
    """Turn a client's `Seed.Create` frame into a real Seed and return the `Seed.Created` verdict.

    Parse + validate the untrusted frame, mint a Seed through the Kernel (authoritative: the Kernel
    owns identity, authz, and persistence), and shape the verdict. A bad frame, a duplicate name, or
    any Kernel refusal becomes an honest `ok:false` verdict with the reason - the engine never
    crashes on client input, and never claims a Seed it did not create. The Seed's kind is folded
    into its purpose (the Kernel has no separate kind field, by design), so intent is not lost."""
    try:
        request = parse_seed_create(data)
    except WorkspaceContractError as exc:
        return seed_created("", False, reason=str(exc))
    purpose = request.description or f"{request.kind} Seed"
    try:
        record = kernel.create_seed(request.name, owner, purpose)
    except BlueprintKernelError as exc:
        return seed_created(request.name, False, reason=str(exc))
    return seed_created(record.identity.name, True, seed_id=record.identity.seed_id)


# --- the planning surface: filed Blueprints -> the client's Blueprint Panel ---------------------


def blueprint_list(
    blueprints: Sequence[Blueprint], *, seed: str | None = None
) -> dict[str, object]:
    """The `Blueprint.List` payload for an engineering Seed: a projection of its filed Blueprints
    (planning specs) into a status-grouped list the client's Blueprint Panel renders.

    Each Blueprint contributes its canonical record (`kernel.blueprint.to_dict`: blueprint_id,
    title, intent, requirements, security, tasks, stack, status) - the real authored fields and
    only those. A Blueprint is a STATIC validated spec, not a live compilation, so this projects no
    "compile progress", phase, or step-execution state: none exists, and inventing it would be
    Vision Theater. `statuses` is the Blueprint count per status label, sorted, so the client groups
    without re-counting (mirrors `Architecture.Map.domains`). Blueprints sort by id for a stable
    list. Pure and offline: it shapes the list it is given, never reads or writes a Blueprint."""
    ordered = sorted(blueprints, key=lambda bp: bp.blueprint_id)
    statuses: Counter[str] = Counter(bp.status for bp in blueprints)
    payload: dict[str, object] = {
        "blueprint_count": len(ordered),
        "statuses": [{"status": name, "count": n} for name, n in sorted(statuses.items())],
        "blueprints": [blueprint_record(bp) for bp in ordered],
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


# --- the deployment surface: the sizing manifest -> the client's Deployment Panel ---------------


def deploy_manifest(manifest: BuildManifest, *, seed: str | None = None) -> dict[str, object]:
    """The `Deploy.Manifest` payload for an engineering Seed: a read-only projection of its
    deployment-sizing manifest (`kernel/seed_package.py::BuildManifest`) - the chosen deployment
    tier, the derived world sizing every downstream generator sizes itself from, and the HONEST
    hardware read (fits one host, or shard across N).

    This is deployment SIZING, not a live cloud deploy: it carries only what `compile_manifest`
    actually derives (all real, nothing authored by hand and nothing invented - No Vision Theater).
    `sizing` is the manifest's own field set (`asdict`) plus the human storage string the client
    would otherwise re-derive. Pure and offline: it shapes the manifest it is given."""
    sizing = asdict(manifest.sizing)
    sizing["storage_human"] = manifest.sizing.storage_human
    payload: dict[str, object] = {
        "schema": manifest.schema_version,
        "project": manifest.project,
        "tier_id": manifest.tier_id,
        "tier_name": manifest.tier_name,
        "hardware": manifest.hardware,
        "sizing": sizing,
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


def deploy_status(
    *,
    version: str,
    seed: str,
    uptime_seconds: float,
    connections: int,
    max_connections: int,
    tls: bool,
) -> dict[str, object]:
    """The `Deploy.Status` payload: the RUNNING server instance's OWN live status - the honest,
    no-cloud slice of a deployment panel. Every field is a real fact the running node knows about
    itself: the engine `version`, the loaded `seed`, its `uptime_seconds`, its live `connections`
    (current / max, from the bulkhead), and whether it is serving over `tls`. This is not a cloud
    provisioning status (no URL, region, or health of an external platform - the engine cannot know
    those and will not invent them); it is the instance reporting itself. Pure: the gateway gathers
    the live values and this shapes them."""
    return {
        "version": version,
        "seed": seed,
        "uptime_seconds": max(0, int(uptime_seconds)),
        "connections": {"current": int(connections), "max": int(max_connections)},
        "tls": bool(tls),
    }


def summarize_test_runs(runs: Sequence[ToolRunResult]) -> dict[str, int] | None:
    """A minimal test summary derived from recorded test runs, or None when there are no tests."""
    test_runs = [run for run in runs if run.kind == "test"]
    if not test_runs:
        return None
    passed = sum(1 for run in test_runs if run.ok)
    failed = sum(1 for run in test_runs if not run.ok)
    return {"passed": passed, "failed": failed, "skipped": 0}


# --- the creation Form: the Engineering Form -> the client's Seed Creation Wizard ---------------


def form_schema(definition: FormDefinition, *, seed: str | None = None) -> dict[str, object]:
    """The `Form.Schema` payload for the creation Wizard: a read-only projection of the Engineering
    Form catalog (`kernel/seedlab/form.py` + `data/seedlab/engineering_form.json`) so the client can
    render the adaptive question set for each product type.

    Each question carries its `prompt`, `kind`, and `required`; `choices` and `applies_when` only
    when the question has them (a text question has neither, and an absent field is a default, never
    an invented one - the same No Vision Theater law as the other builders). Product types keep the
    catalog's order (a dict preserves insertion order), so the client renders them as filed. The
    `schema` is the Form's real wire version, so a client reads (or refuses) it knowingly. Pure and
    offline: it shapes the definition it is given, never loads or mutates one."""
    questions: dict[str, dict[str, object]] = {}
    for qid, question in definition.questions.items():
        entry: dict[str, object] = {
            "prompt": question.prompt,
            "kind": question.kind,
            "required": question.required,
        }
        if question.choices:
            entry["choices"] = list(question.choices)
        if question.applies_when:
            entry["applies_when"] = {key: value for key, value in question.applies_when}
        questions[qid] = entry
    product_types = [
        {
            "id": pt.id,
            "name": pt.name,
            "description": pt.description,
            "question_ids": list(pt.question_ids),
            "domain_modules": list(pt.domain_modules),
        }
        for pt in definition.product_types.values()
    ]
    payload: dict[str, object] = {
        "schema": FORM_SPEC_SCHEMA,
        "common_question_ids": list(definition.common_question_ids),
        "questions": questions,
        "product_types": product_types,
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


@dataclass(frozen=True)
class FormSubmitRequest:
    """A validated `Form.Submit` request from a client: the chosen `product_type` and the `answers`
    map. The engine does not trust the wire, so this is the checked shape a raw frame is parsed into
    before the Engineering Form (which re-validates authoritatively) ever sees it."""

    product_type: str
    answers: dict[str, object]


def parse_form_submit(data: object) -> FormSubmitRequest:
    """Parse an untrusted `Form.Submit` frame into a validated request, or fail loud
    (`WorkspaceContractError`).

    The frame must be an object naming a non-empty `product_type` and an `answers` object (an empty
    answers map is allowed - the Form re-validates and fails on any missing required answer). The
    engine re-checks the shape the client already checked (defense in depth)."""
    if not isinstance(data, dict):
        raise WorkspaceContractError("Form.Submit: payload must be an object")
    product_type = data.get("product_type")
    if not isinstance(product_type, str) or not product_type.strip():
        raise WorkspaceContractError("Form.Submit: 'product_type' must be a non-empty string")
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        raise WorkspaceContractError("Form.Submit: 'answers' must be an object")
    return FormSubmitRequest(product_type=product_type.strip(), answers=dict(answers))


def create_from_form_submit(
    kernel: BlueprintKernel, definition: FormDefinition, data: object, *, owner: str
) -> dict[str, object]:
    """Turn a client's `Form.Submit` frame into a real Seed and return the `Seed.Created` verdict.

    Parse + validate the untrusted frame, validate its answers through the Engineering Form (which
    owns the authoritative check, including the adaptive `applies_when` branch and every choice
    range), then mint a Seed through the Kernel carrying the Form's product type and selected domain
    modules. A bad frame, a failed Form validation, or any Kernel refusal becomes an honest
    `ok:false` verdict - the engine never crashes on client input, and never claims a Seed it did
    not create.

    The engine is authoritative on identity: the authenticated `owner` is the Seed's true owner, so
    the client's `owner` answer is OVERRIDDEN (never trusted) before the Form validates - a client
    cannot mint a Seed under another account by typing a name in a box."""
    try:
        request = parse_form_submit(data)
    except WorkspaceContractError as exc:
        return seed_created("", False, reason=str(exc))
    answers = {**request.answers, "owner": owner}
    try:
        spec = EngineeringForm(definition).build_spec(request.product_type, answers)
    except FormError as exc:
        claimed = request.answers.get("name")
        name = claimed if isinstance(claimed, str) else ""
        return seed_created(name, False, reason=str(exc))
    try:
        record = kernel.create_seed(
            spec.name,
            owner,
            spec.purpose,
            product_type=spec.product_type,
            domain_modules=spec.domain_modules,
        )
    except BlueprintKernelError as exc:
        return seed_created(spec.name, False, reason=str(exc))
    return seed_created(record.identity.name, True, seed_id=record.identity.seed_id)


# --- the aggregate a gateway would push for a Seed ----------------------------------------------


def workspace_packages(
    record: BlueprintRecord,
    *,
    source: SourceRecord | None = None,
    files: list[str] | None = None,
    model: ProjectModel | None = None,
    runs: Sequence[ToolRunResult] | None = None,
    artifacts: Sequence[Mapping[str, object]] | None = None,
    branch: str | None = None,
    modules: Sequence[Mapping[str, object]] | None = None,
    findings: Sequence[Mapping[str, object]] | None = None,
    blueprints: Sequence[Blueprint] | None = None,
    manifest: BuildManifest | None = None,
) -> list[tuple[str, dict[str, object]]]:
    """The (package, payload) pairs a gateway emits for an engineering Seed: always its Project
    Status, plus a Source Tree when a source is registered, a Model Schema when a model is
    extracted, a Build Report when tool runs have happened, an Architecture Map when a module
    registry is supplied, a Research Findings package when the Seed has research to report, and a
    Blueprint List when the Seed has filed Blueprints, and a Deploy Manifest when a deployment-
    sizing manifest is supplied. The one call a live driver would loop over to push the workspace;
    each pair frames with `kernel.gmcp.gmcp_frame`. Artifact entries are passed only when a real
    artifact registry supplied them; absent entries remain absent in `Build.Report`."""
    seed = record.identity.name
    packages: list[tuple[str, dict[str, object]]] = [
        (PROJECT_STATUS_PACKAGE, project_status(record, branch=branch or _source_branch(source)))
    ]
    if source is not None:
        packages.append((SOURCE_TREE_PACKAGE, source_tree(source, files or [], seed=seed)))
        packages.append((SOURCE_CONNECTION_PACKAGE, source_connection_package(source, seed=seed)))
    if model is not None:
        packages.append((MODEL_SCHEMA_PACKAGE, model_schema(model, seed=seed)))
    if runs:
        packages.append(
            (
                BUILD_REPORT_PACKAGE,
                build_report(
                    runs,
                    seed=seed,
                    tests=summarize_test_runs(runs),
                    artifacts=[dict(entry) for entry in artifacts] if artifacts else None,
                ),
            )
        )
    if modules is not None:
        packages.append((ARCHITECTURE_MAP_PACKAGE, architecture_map(modules, seed=seed)))
    if findings is not None:
        packages.append((RESEARCH_FINDINGS_PACKAGE, research_findings(findings, seed=seed)))
    if blueprints is not None:
        packages.append((BLUEPRINT_LIST_PACKAGE, blueprint_list(blueprints, seed=seed)))
    if manifest is not None:
        packages.append((DEPLOY_MANIFEST_PACKAGE, deploy_manifest(manifest, seed=seed)))
    return packages


def _source_branch(source: SourceRecord | None) -> str | None:
    """The registered source's branch, if a source is given and it is under version control."""
    return source.branch if source is not None else None
