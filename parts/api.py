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

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import select

from parts.accounts import account_has_owner, account_password_ok
from parts.blueprint import load_all as load_blueprints
from parts.characters import set_rank
from parts.dashboard import router as dashboard_router
from parts.db import CharacterRow, open_archive_session
from parts.login_guard import LoginGuard
from parts.ranks import RANK_ORDER
from parts.shelf.observability import install_observability
from parts.world import WORLD

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "alive", "engine": "codeforge"}


@app.get("/characters", response_model=list[Hero])
def characters() -> list[Hero]:
    """Every saved hero, straight from the canonical table."""
    with open_archive_session() as db:
        archive_rows = db.scalars(select(CharacterRow)).all()
    return [
        Hero(name=row.name, job=row.job, level=row.level, rank=row.rank, location=row.location)
        for row in archive_rows
    ]


@app.get("/world/rooms", response_model=list[Room])
def rooms() -> list[Room]:
    """The seed-born room graph."""
    return [
        Room(label=label, name=room["name"], exits=dict(room["exits"]))
        for label, room in WORLD.items()
    ]


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
def grant(body: GrantRequest, _account: Annotated[str, Depends(_require_owner)]) -> dict[str, str]:
    """Owner-authenticated rank change. Same gate order as @grant."""
    if body.rank not in RANK_ORDER:
        raise HTTPException(status_code=422, detail=f"'{body.rank}' is not a rank.")
    message = set_rank(body.name, body.rank)
    if message.startswith("No saved character"):
        raise HTTPException(status_code=404, detail=message)
    return {"result": message}
