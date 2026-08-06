"""CARD: api -- an HTTP window onto the canonical world (FastAPI).

The engine's third driver -- but a deliberately different kind: it
reads canonical STORAGE (SQL) and world data (seeds), not the
gateway's live sessions, because separate processes share databases,
not memory. Live rosters need a shared bus: a future card, named.

FastAPI gives typed request/response models and a free interactive
/docs page. Admin mutations require HTTP Basic auth with an account
that owns an owner-ranked character -- authorization before
capability, same law as the @-verbs.
"""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import select

from kernel.blueprint import load_all as load_blueprints
from kernel.dashboard import router as dashboard_router
from kernel.hardware_lifecycle import HardwareRegistry, default_registry_path
from kernel.login_guard import LoginGuard
from kernel.platform import current_platform_status
from kernel.seedlab.artifact_registry import configured_artifact_store
from kernel.seedlab.artifact_store import ArtifactStore
from kernel.seedlab.creator_draft import CreatorDraftError
from kernel.seedlab.kernel import SeedKernel, SeedKernelError
from kernel.seedlab.manifest_registry import configured_manifest_evidence_store
from kernel.seedlab.model_store import ModelStore, configured_model_store
from kernel.seedlab.registry import configured_seed_store
from kernel.seedlab.task import TaskError, TaskRecord, configured_task_store
from kernel.seedlab.tool_runner import RunLog, configured_run_log
from kernel.seedlab.workshop_services import CreatorWorkshopService
from kernel.seedlab.workspace_contract import (
    build_workspace_contract,
)
from kernel.shelf import cursor as cursor_part
from kernel.shelf import precondition as precond
from kernel.shelf.observability import install_observability
from kernel.world.accounts import account_has_owner, account_password_ok
from kernel.world.characters import set_rank
from kernel.world.db import CharacterRow, open_archive_session
from kernel.world.ranks import RANK_ORDER
from kernel.world.world import WORLD


@asynccontextmanager
async def _startup_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Refuse direct ASGI startup when persistence is behind the model schema."""
    from kernel.platform import validate_startup_schema

    validate_startup_schema()
    yield


app = FastAPI(
    title="CodeForge Admin API",
    description="A window onto the canonical world: saved heroes, the room graph, "
    "and owner-authenticated administration.",
    version="0.1.0",
    lifespan=_startup_lifespan,
)

# The portfolio Lens: GET / (server-rendered readiness board) + GET /api/status (JSON twin).
app.include_router(dashboard_router)

# Telemetry: structured request logs (structlog) + Prometheus /metrics.
install_observability(app)

_basic = HTTPBasic()
# Reuse the Hardware Store throttle (parts/login_guard, built on the token-bucket part): brute-force
# protection for this surface, the same as the telnet gateway's per-IP lockout. 5-attempt burst,
# then one every 30s. A shared instance across requests; a dependency seam so tests isolate it.
_login_guard = LoginGuard()


def get_login_guard() -> LoginGuard:
    """Dependency seam for the brute-force throttle - overridden in tests for per-test isolation."""
    return _login_guard


async def _get_login_guard() -> LoginGuard:
    """Async adapter keeps the dependency out of AnyIO's sync worker pool."""
    return get_login_guard()


async def _require_owner(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials, Depends(_basic)],
    guard: Annotated[LoginGuard, Depends(_get_login_guard)],
) -> str:
    """HTTP Basic: the account must exist, the password must match, and
    the account must hold an owner-ranked character. One generic 401."""
    # Throttle by client IP FIRST, before the expensive pbkdf2 - so a brute-force attempt (and its
    # CPU cost) is capped without even paying the hash, and a barred caller is turned away fast.
    client = request.client.host if request.client else "unknown"
    decision = guard.attempt(client)
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(int(decision.retry_after) + 1)},
        )
    # account_password_ok is constant-time whether or not the account exists (a decoy hash levels
    # the pbkdf2 cost in parts/accounts), so this gate does not leak account existence by timing.
    # One generic 401, never saying which part failed.
    ok = account_password_ok(credentials.username, credentials.password) and account_has_owner(
        credentials.username
    )
    if not ok:
        raise HTTPException(status_code=401, detail="Not authorized.")
    return credentials.username


class Hero(BaseModel):
    name: str
    job: str
    level: int
    rank: str
    location: str


class Room(BaseModel):
    label: str
    name: str
    exits: dict[str, str]


class GrantRequest(BaseModel):
    name: str
    rank: str


class BlueprintSummary(BaseModel):
    blueprint_id: str
    title: str
    intent: str
    status: str
    requirement_count: int


class WorkshopPartSummary(BaseModel):
    id: str
    name: str
    category: str
    maturity: str
    risk: str
    source_status: str
    license: str


class WorkshopCatalogPayload(BaseModel):
    service: str
    parts: list[WorkshopPartSummary]


class WorkspaceSeedSummary(BaseModel):
    id: str
    name: str
    owner: str
    status: str
    purpose: str


class WorkspacePackageSummary(BaseModel):
    package: str
    payload: dict[str, Any]


class WorkspaceStateSummary(BaseModel):
    seed_id: str
    sources: list[str]
    connectors: list[str]
    models: list[str]
    builds: list[str]
    tests: list[str]
    targets: list[str]
    risks: list[str]
    decisions: list[str]


class WorkspaceContractPayload(BaseModel):
    contract_version: str
    seed: WorkspaceSeedSummary
    project: dict[str, Any]
    project_state: WorkspaceStateSummary
    packages: list[WorkspacePackageSummary]


class SeedLabConnectRequest(BaseModel):
    path: str


class SeedLabDisconnectRequest(BaseModel):
    source_id: str


class SeedLabDraftCreateRequest(BaseModel):
    draft_id: str
    payload: dict[str, Any]


class SeedLabDraftEditRequest(BaseModel):
    changes: dict[str, Any]


class SeedLabDraftTransitionRequest(BaseModel):
    target: str


class SeedLabTaskCreateRequest(BaseModel):
    task_id: str
    title: str
    description: str
    source_proposal: str = ""
    evidence_ids: list[str] = []


class PlatformComponentPayload(BaseModel):
    name: str
    state: str
    detail: str


class PlatformStatusPayload(BaseModel):
    seed: str
    selection_source: str
    components: list[PlatformComponentPayload]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "alive", "engine": "codeforge"}


@app.get("/api/platform/status", response_model=PlatformStatusPayload)
async def platform_status() -> PlatformStatusPayload:
    """The read-only startup/runtime contract consumed by operational clients."""
    return PlatformStatusPayload.model_validate(current_platform_status().to_dict())


class CharacterPage(BaseModel):
    items: list[Hero]
    next_cursor: str | None


def _hero(row: CharacterRow) -> Hero:
    return Hero(name=row.name, job=row.job, level=row.level, rank=row.rank, location=row.location)


def _character_etag(row: CharacterRow) -> precond.ETag:
    """A content ETag over the hero's mutable state (no version column needed)."""
    state = f"{row.name}|{row.job}|{row.level}|{row.rank}|{row.location}".encode()
    return precond.etag_for_payload(state)


def _seedlab_home() -> Path:
    return Path(os.environ.get("SEEDLAB_HOME", ".seedlab"))


def _seedlab_kernel() -> SeedKernel:
    return SeedKernel(configured_seed_store(_seedlab_home()))


def _seedlab_model_store() -> ModelStore:
    return configured_model_store(_seedlab_home())


def _seedlab_run_log() -> RunLog:
    return configured_run_log(_seedlab_home())


def _seedlab_artifact_store() -> ArtifactStore:
    return configured_artifact_store(_seedlab_home())


def _seedlab_workshop() -> CreatorWorkshopService:
    return CreatorWorkshopService.durable(_seedlab_home() / "workshop")


@app.get("/characters", response_model=list[Hero])
async def characters() -> list[Hero]:
    """Every saved hero, straight from the canonical table."""
    with open_archive_session() as db:
        archive_rows = db.scalars(select(CharacterRow)).all()
    return [_hero(row) for row in archive_rows]


@app.get("/characters/page", response_model=CharacterPage)
async def characters_page(limit: int = 20, after: str | None = None) -> CharacterPage:
    """Keyset-paginated heroes (stable under concurrent inserts, O(1) deep pages).

    `after` is the opaque cursor from a previous page's `next_cursor`; heroes are
    ordered by name (the unique key). Reuses the Cursor Hardware Store part.
    """
    try:
        page_size = cursor_part.validate_size(limit)
    except cursor_part.CursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    boundary_name = ""
    if after is not None:
        try:
            _, boundary_name = cursor_part.decode_cursor(after)
        except cursor_part.CursorError as exc:
            raise HTTPException(status_code=400, detail=f"bad cursor: {exc}") from exc
    with open_archive_session() as db:
        query = select(CharacterRow).order_by(CharacterRow.name)
        if after is not None:
            query = query.where(CharacterRow.name > boundary_name)
        rows = db.scalars(query.limit(page_size + 1)).all()  # +1 to detect a next page
    has_more = len(rows) > page_size
    window = rows[:page_size]
    next_cursor = None
    if has_more and window:
        last = window[-1]
        next_cursor = cursor_part.encode_cursor(last.name, last.name)
    return CharacterPage(items=[_hero(row) for row in window], next_cursor=next_cursor)


@app.get("/characters/{name}", response_model=Hero)
async def character(name: str, response: Response) -> Hero:
    """One hero by name, with an `ETag` header for optimistic-concurrency edits."""
    with open_archive_session() as db:
        row = db.scalars(select(CharacterRow).where(CharacterRow.name == name)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No saved character named '{name}'.")
    response.headers["ETag"] = _character_etag(row).format()
    return _hero(row)


@app.get("/world/rooms", response_model=list[Room])
async def rooms() -> list[Room]:
    """The seed-born room graph."""
    return [
        Room(label=label, name=room["name"], exits=dict(room["exits"]))
        for label, room in WORLD.items()
    ]


@app.get("/api/seedlab/workspaces/{seed_id}")
async def seedlab_workspace(seed_id: str) -> dict[str, object]:
    """The structured SeedLab workspace contract a client can render."""
    kernel = _seedlab_kernel()
    try:
        kernel.get(seed_id)
    except SeedKernelError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    models = _seedlab_model_store().all_for_seed(seed_id)
    contract = build_workspace_contract(
        seed_id,
        root=_seedlab_home(),
        model=models[-1] if models else None,
        runs=_seedlab_run_log().for_seed(seed_id),
        artifacts=_seedlab_artifact_store().all_for_seed(seed_id),
        manifest_evidence=_workspace_manifest_evidence(seed_id),
        hardware_records=_workspace_hardware_records(),
    )
    return contract.to_dict()


@app.post("/api/seedlab/workspaces/{seed_id}/connect")
async def seedlab_connect(
    seed_id: str,
    request: SeedLabConnectRequest,
    account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Connect and model a source through the authoritative Seed workspace boundary."""
    from kernel.seedlab.workspace_verb import workspace_command

    kernel = _seedlab_kernel()
    try:
        kernel.require_owner(seed_id, account)
    except SeedKernelError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = workspace_command(
        type("ApiSession", (), {"account": account, "player_id": account})(),
        f"connect {seed_id} {request.path}",
        kernel=kernel,
    )
    if result.startswith("workspace:"):
        raise HTTPException(status_code=400, detail=result.removeprefix("workspace: ").strip())
    return (
        build_workspace_contract(
            seed_id,
            root=_seedlab_home(),
            model=_seedlab_model_store().all_for_seed(seed_id)[-1],
            runs=_seedlab_run_log().for_seed(seed_id),
            artifacts=_seedlab_artifact_store().all_for_seed(seed_id),
            manifest_evidence=_workspace_manifest_evidence(seed_id),
            hardware_records=_workspace_hardware_records(),
        )
    ).to_dict()


@app.post("/api/seedlab/workspaces/{seed_id}/disconnect")
async def seedlab_disconnect(
    seed_id: str,
    request: SeedLabDisconnectRequest,
    account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Persist a connector removal tombstone and return the resulting contract."""
    from kernel.seedlab.workspace_verb import workspace_command

    kernel = _seedlab_kernel()
    try:
        kernel.require_owner(seed_id, account)
    except SeedKernelError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = workspace_command(
        type("ApiSession", (), {"account": account, "player_id": account})(),
        f"disconnect {seed_id} {request.source_id}",
        kernel=kernel,
    )
    if result.startswith("workspace:"):
        raise HTTPException(status_code=400, detail=result.removeprefix("workspace: ").strip())
    return build_workspace_contract(
        seed_id,
        root=_seedlab_home(),
        runs=_seedlab_run_log().for_seed(seed_id),
        artifacts=_seedlab_artifact_store().all_for_seed(seed_id),
        manifest_evidence=_workspace_manifest_evidence(seed_id),
        hardware_records=_workspace_hardware_records(),
    ).to_dict()


def _workspace_contract(seed_id: str) -> dict[str, object]:
    """Build the authoritative post-mutation contract shared by every workspace write."""
    models = _seedlab_model_store().all_for_seed(seed_id)
    return build_workspace_contract(
        seed_id,
        root=_seedlab_home(),
        model=models[-1] if models else None,
        runs=_seedlab_run_log().for_seed(seed_id),
        artifacts=_seedlab_artifact_store().all_for_seed(seed_id),
        manifest_evidence=_workspace_manifest_evidence(seed_id),
        hardware_records=_workspace_hardware_records(),
    ).to_dict()


@app.post("/api/seedlab/workspaces/{seed_id}/drafts")
async def seedlab_create_draft(
    seed_id: str,
    request: SeedLabDraftCreateRequest,
    account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Create an isolated Creator Workshop draft and return its authoritative projection."""
    kernel = _seedlab_kernel()
    try:
        kernel.require_owner(seed_id, account)
        CreatorWorkshopService.durable(_seedlab_home() / "workshop").create_draft(
            request.draft_id,
            seed_id,
            account,
            request.payload,
        )
    except (SeedKernelError, CreatorDraftError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _workspace_contract(seed_id)


@app.post("/api/seedlab/workspaces/{seed_id}/tasks")
async def seedlab_create_task(
    seed_id: str,
    request: SeedLabTaskCreateRequest,
    account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Create an owner-authenticated implementation task and return its workspace projection."""
    kernel = _seedlab_kernel()
    try:
        kernel.require_owner(seed_id, account)
        task = configured_task_store(_seedlab_home()).create(
            TaskRecord(
                task_id=request.task_id,
                seed_id=seed_id,
                owner_id=account,
                title=request.title,
                description=request.description,
                source_proposal=request.source_proposal,
                evidence_ids=tuple(request.evidence_ids),
            )
        )
    except (SeedKernelError, TaskError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"task": task.to_dict(), "workspace": _workspace_contract(seed_id)}


@app.post("/api/seedlab/workspaces/{seed_id}/drafts/{draft_id}/edit")
async def seedlab_edit_draft(
    seed_id: str,
    draft_id: str,
    request: SeedLabDraftEditRequest,
    account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Edit a created draft through the durable Creator Workshop service."""
    kernel = _seedlab_kernel()
    try:
        kernel.require_owner(seed_id, account)
        service = CreatorWorkshopService.durable(_seedlab_home() / "workshop")
        current = service.drafts.get(draft_id)
        if current.seed_id != seed_id:
            raise CreatorDraftError("draft does not belong to this Seed")
        service.edit_draft(draft_id, account, request.changes)
    except (SeedKernelError, CreatorDraftError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _workspace_contract(seed_id)


@app.post("/api/seedlab/workspaces/{seed_id}/drafts/{draft_id}/transition")
async def seedlab_transition_draft(
    seed_id: str,
    draft_id: str,
    request: SeedLabDraftTransitionRequest,
    account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Advance a draft only through the CreatorDraft state machine."""
    kernel = _seedlab_kernel()
    try:
        kernel.require_owner(seed_id, account)
        service = CreatorWorkshopService.durable(_seedlab_home() / "workshop")
        current = service.drafts.get(draft_id)
        if current.seed_id != seed_id:
            raise CreatorDraftError("draft does not belong to this Seed")
        service.transition_draft(draft_id, request.target, account)
    except (SeedKernelError, CreatorDraftError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _workspace_contract(seed_id)


@app.get("/api/seedlab/proofs/{seed_id}")
async def seedlab_platform_proof(
    seed_id: str,
    _account: Annotated[str, Depends(_require_owner)],
) -> dict[str, object]:
    """Return the exact durable first-platform proof to an authenticated owner.

    The Master Client receives a read-only projection of evidence. It never executes, repairs,
    redeploys, or treats the proof as authority; the Seed and deployment records remain owned by
    their existing services.
    """
    if Path(seed_id).name != seed_id or seed_id in {".", ".."}:
        raise HTTPException(status_code=400, detail="invalid Seed id")
    path = _seedlab_home() / "proof" / "evidence" / f"platform-proof-{seed_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no platform proof for Seed {seed_id!r}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500, detail="platform proof evidence is unavailable"
        ) from exc
    if not isinstance(payload, dict) or payload.get("seed_id") != seed_id:
        raise HTTPException(
            status_code=409, detail="platform proof evidence does not match the Seed"
        )
    return payload


def _workspace_manifest_evidence(seed_id: str):
    """Read the canonical durable evidence projection without creating empty state."""
    records = configured_manifest_evidence_store(_seedlab_home()).all_for_seed(seed_id)
    return records or None


def _workspace_hardware_records():
    """Read the configured Hardware registry; the workspace never activates components."""
    path = default_registry_path()
    if not path.is_file():
        return None
    return HardwareRegistry(path).all()


@app.get("/api/blueprints", response_model=list[BlueprintSummary])
async def blueprints() -> list[BlueprintSummary]:
    """Every filed Blueprint, summarized. The typed contract a front end lists from."""
    return [
        BlueprintSummary(
            blueprint_id=b.blueprint_id,
            title=b.title,
            intent=b.intent,
            status=b.status,
            requirement_count=len(b.requirements),
        )
        for b in load_blueprints()
    ]


@app.get("/api/creator-workshop/catalog", response_model=WorkshopCatalogPayload)
async def creator_workshop_catalog() -> WorkshopCatalogPayload:
    """Read the authoritative Hardware Store catalog through the Workshop service boundary."""
    return WorkshopCatalogPayload(
        service="creator-workshop",
        parts=[
            WorkshopPartSummary(
                id=part.id,
                name=part.name,
                category=part.category,
                maturity=part.maturity,
                risk=part.risk,
                source_status=part.source_status,
                license=part.license,
            )
            for part in _seedlab_workshop().shelf()
        ],
    )


@app.post("/admin/grant")
async def grant(
    body: GrantRequest,
    _account: Annotated[str, Depends(_require_owner)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, str]:
    """Owner-authenticated rank change. Same gate order as @grant.

    Optional optimistic concurrency: if the client sends an `If-Match` ETag (from
    `GET /characters/{name}`), the grant is rejected 412 when the hero changed since
    it was read, so a stale edit never clobbers a concurrent one. Reuses the
    Precondition Hardware Store part.
    """
    if body.rank not in RANK_ORDER:
        raise HTTPException(status_code=422, detail=f"'{body.rank}' is not a rank.")
    if if_match is not None:
        with open_archive_session() as db:
            row = db.scalars(select(CharacterRow).where(CharacterRow.name == body.name)).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"No saved character named '{body.name}'.")
        try:
            precond.if_match(_character_etag(row), if_match)
        except precond.PreconditionError as exc:
            raise HTTPException(status_code=400, detail=f"bad If-Match: {exc}") from exc
        except precond.PreconditionFailed as exc:
            raise HTTPException(status_code=412, detail=str(exc)) from exc
    message = set_rank(body.name, body.rank)
    if message.startswith("No saved character"):
        raise HTTPException(status_code=404, detail=message)
    return {"result": message}
