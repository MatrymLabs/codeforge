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

import secrets as _secrets
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import select

from parts.accounts import account_has_owner, account_password_ok
from parts.characters import set_rank
from parts.db import CharacterRow, get_session
from parts.ranks import RANK_ORDER
from parts.world import WORLD

app = FastAPI(
    title="CodeForge Admin API",
    description="A window onto the canonical world: saved heroes, the room graph, "
    "and owner-authenticated administration.",
    version="0.1.0",
)

_basic = HTTPBasic()


def _require_owner(credentials: Annotated[HTTPBasicCredentials, Depends(_basic)]) -> str:
    """HTTP Basic: the account must exist, the password must match, and
    the account must hold an owner-ranked character. One generic 401."""
    ok = account_password_ok(credentials.username, credentials.password) and account_has_owner(
        credentials.username
    )
    if not ok:
        # burn comparable time either way; never say which part failed
        _secrets.compare_digest("a", "b")
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "alive", "engine": "codeforge"}


@app.get("/characters", response_model=list[Hero])
def characters() -> list[Hero]:
    """Every saved hero, straight from the canonical table."""
    with get_session() as db:
        rows = db.scalars(select(CharacterRow)).all()
    return [
        Hero(name=r.name, job=r.job, level=r.level, rank=r.rank, location=r.location) for r in rows
    ]


@app.get("/world/rooms", response_model=list[Room])
def rooms() -> list[Room]:
    """The seed-born room graph."""
    return [
        Room(label=label, name=room["name"], exits=dict(room["exits"]))
        for label, room in WORLD.items()
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
