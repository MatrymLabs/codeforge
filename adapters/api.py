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

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import select

from kernel.blueprint import load_all as load_blueprints
from kernel.dashboard import router as dashboard_router
from kernel.login_guard import LoginGuard
from kernel.seedlab.artifact_store import FileArtifactStore
from kernel.seedlab.kernel import BlueprintKernel, BlueprintKernelError, FileSeedStore
from kernel.seedlab.model_store import FileModelStore
from kernel.seedlab.tool_runner import FileRunLog
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

app = FastAPI(
    title="CodeForge Admin API",
    description="A window onto the canonical world: saved heroes, the room graph, "
    "and owner-authenticated administration.",
    version="0.1.0",
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


def _require_owner(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials, Depends(_basic)],
    guard: Annotated[LoginGuard, Depends(get_login_guard)],
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "alive", "engine": "codeforge"}


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


def _seedlab_kernel() -> BlueprintKernel:
    return BlueprintKernel(FileSeedStore(_seedlab_home() / "seeds"))


def _seedlab_model_store() -> FileModelStore:
    return FileModelStore(_seedlab_home() / "models")


def _seedlab_run_log() -> FileRunLog:
    return FileRunLog(_seedlab_home() / "runs")


def _seedlab_artifact_store() -> FileArtifactStore:
    return FileArtifactStore(_seedlab_home() / "artifacts")


@app.get("/characters", response_model=list[Hero])
def characters() -> list[Hero]:
    """Every saved hero, straight from the canonical table."""
    with open_archive_session() as db:
        archive_rows = db.scalars(select(CharacterRow)).all()
    return [_hero(row) for row in archive_rows]


@app.get("/characters/page", response_model=CharacterPage)
def characters_page(limit: int = 20, after: str | None = None) -> CharacterPage:
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
def character(name: str, response: Response) -> Hero:
    """One hero by name, with an `ETag` header for optimistic-concurrency edits."""
    with open_archive_session() as db:
        row = db.scalars(select(CharacterRow).where(CharacterRow.name == name)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No saved character named '{name}'.")
    response.headers["ETag"] = _character_etag(row).format()
    return _hero(row)


@app.get("/world/rooms", response_model=list[Room])
def rooms() -> list[Room]:
    """The seed-born room graph."""
    return [
        Room(label=label, name=room["name"], exits=dict(room["exits"]))
        for label, room in WORLD.items()
    ]


@app.get("/api/seedlab/workspaces/{seed_id}")
def seedlab_workspace(seed_id: str) -> dict[str, object]:
    """The structured SeedLab workspace contract a client can render."""
    kernel = _seedlab_kernel()
    try:
        kernel.get(seed_id)
    except BlueprintKernelError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    models = _seedlab_model_store().all_for_seed(seed_id)
    contract = build_workspace_contract(
        seed_id,
        root=_seedlab_home(),
        model=models[-1] if models else None,
        runs=_seedlab_run_log().for_seed(seed_id),
        artifacts=_seedlab_artifact_store().all_for_seed(seed_id),
    )
    return contract.to_dict()


@app.get("/api/blueprints", response_model=list[BlueprintSummary])
def blueprints() -> list[BlueprintSummary]:
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


@app.post("/admin/grant")
def grant(
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
