"""CARD: workspace_gmcp -- project an engineering Seed's state into the Master Client's workspace
GMCP contracts, and turn a client's create request into a real Seed.

The Master Client renders four read-only Engineering Workspace views (Project Hub, Source Explorer,
Model view, Build Report) plus a Seed-creation flow, each fed by a named GMCP package. Stages 0-2 of
the Seed Interface Directive taught this engine the `Seed.Hello` handshake (parts/gmcp.py); this
card teaches it the WORKSPACE half: it reads the seedlab models that already exist and shapes them
into the exact packages the client parses, and it reads a client's `Seed.Create` request and mints a
real Seed through the Kernel.

Two laws hold, the same as parts/gmcp.py:

- **State is canonical; a report is a read-only projection.** Each builder takes a seedlab record
  (`SeedRecord`, `SourceRecord`, `ProjectModel`) and returns a JSON-able dict - never a second
  source of truth, never a mutation. The gateway owns the socket and decides when to send.
- **Honest by construction (No Vision Theater).** A builder emits only what THIS card wires. Per-
  entity fields are not modeled yet, so `Model.Schema` carries entity names with empty field lists.
  `Build.Report` is deliberately NOT emitted here: a build/test model landed in a parallel seedlab
  stage (`tool_runner`), but wiring its results into the client contract is a follow-up, not this
  slice - and fabricating a "run" would be a lie. When those are wired, the packages fill; the
  contract shape does not change.

The client's parsers are defensive (a missing field takes a default, a bad frame is surfaced), so
the engine emits the subset it has and the client renders it. Pure and offline: the only side effect
is through an injected `SeedKernel` (a test injects an in-memory store); nothing touches a socket.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

from parts.seedlab.kernel import SeedKernel, SeedKernelError, SeedRecord
from parts.seedlab.project_model import ProjectModel
from parts.seedlab.source_connector import SourceRecord

# --- the workspace package names (must match the client's core/*.py PACKAGE constants) -----------
#: An engineering Seed's project status -> the client's Project Hub (core/project.py).
PROJECT_STATUS_PACKAGE = "Project.Status"
#: An engineering Seed's source tree -> the client's Source Explorer (core/source.py).
SOURCE_TREE_PACKAGE = "Source.Tree"
#: An engineering Seed's data model -> the client's Model view (core/model.py).
MODEL_SCHEMA_PACKAGE = "Model.Schema"
#: A client's request to CREATE a Seed (client -> engine); the verdict below is the reply.
SEED_CREATE_PACKAGE = "Seed.Create"
#: The engine's verdict on a create request (engine -> client), read by core/seed_create.py.
SEED_CREATED_PACKAGE = "Seed.Created"

#: The kinds of Seed a client may ask to create (matches the client's SEED_KINDS).
SEED_KINDS = ("engineering", "game")


class WorkspaceContractError(ValueError):
    """A `Seed.Create` request that is not a valid request object -- fail loud, never mint a Seed
    from a malformed or untrusted frame. (The client validated its own input; the engine, which does
    not trust the wire, validates again.)"""


# --- projecting seedlab state into the read-only view contracts ---------------------------------


def project_status(
    record: SeedRecord,
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


def model_schema(model: ProjectModel, *, seed: str | None = None) -> dict[str, object]:
    """The `Model.Schema` payload for an extracted project model: its entities. The seedlab model
    records entity NAMES (not yet their fields - that is a later extractor stage), so each entity is
    emitted with an empty field list; the client renders "Entity (0 fields)" honestly until the
    richer extractor lands. `seed` labels the project (defaults to the model's own identity)."""
    return {
        "seed": seed or model.identity,
        "entities": [{"name": name, "fields": []} for name in model.entities],
    }


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


def create_from_request(kernel: SeedKernel, data: object, *, owner: str) -> dict[str, object]:
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
    except SeedKernelError as exc:
        return seed_created(request.name, False, reason=str(exc))
    return seed_created(record.identity.name, True, seed_id=record.identity.seed_id)


# --- the aggregate a gateway would push for a Seed ----------------------------------------------


def workspace_packages(
    record: SeedRecord,
    *,
    source: SourceRecord | None = None,
    files: list[str] | None = None,
    model: ProjectModel | None = None,
    branch: str | None = None,
) -> list[tuple[str, dict[str, object]]]:
    """The (package, payload) pairs a gateway emits for an engineering Seed: always its Project
    Status, plus a Source Tree when a source is registered and a Model Schema when a model is
    extracted. The one call a live driver would loop over to push the workspace; each pair frames
    with `parts.gmcp.gmcp_frame`. Build.Report is absent until the engine models a real build/test
    run (No Vision Theater)."""
    seed = record.identity.name
    packages: list[tuple[str, dict[str, object]]] = [
        (PROJECT_STATUS_PACKAGE, project_status(record, branch=branch or _source_branch(source)))
    ]
    if source is not None:
        packages.append((SOURCE_TREE_PACKAGE, source_tree(source, files or [], seed=seed)))
    if model is not None:
        packages.append((MODEL_SCHEMA_PACKAGE, model_schema(model, seed=seed)))
    return packages


def _source_branch(source: SourceRecord | None) -> str | None:
    """The registered source's branch, if a source is given and it is under version control."""
    return source.branch if source is not None else None
