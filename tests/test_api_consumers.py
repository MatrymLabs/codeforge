"""Real-consumer tests for the Cursor + Precondition Hardware Store parts, wired into the HTTP API.

- GET /characters/page: keyset pagination (Cursor part) over the canonical table.
- GET /characters/{name} + POST /admin/grant with If-Match: optimistic concurrency (Precondition
  part) so a stale rank change is rejected 412 instead of clobbering a concurrent one.
"""

import pytest

from adapters.api import _get_login_guard, app
from kernel.login_guard import LoginGuard
from kernel.world.accounts import adopt, register
from kernel.world.characters import save_character, set_rank
from kernel.world.session import SESSIONS, Session
from tests.sync_test_client import TestClient


@pytest.fixture(autouse=True)
def _fresh():
    SESSIONS.clear()
    guard = LoginGuard()

    async def override_guard() -> LoginGuard:
        return guard

    app.dependency_overrides[_get_login_guard] = override_guard
    yield
    app.dependency_overrides.clear()
    SESSIONS.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _save(name: str, level: int = 1) -> None:
    SESSIONS[name] = Session(player_id=name, location="courtyard", named=True, level=level)
    save_character(SESSIONS[name])
    SESSIONS.clear()


def _owner(char="matrym", account="matlabs", pw="swordfish"):
    _save(char, level=2)
    register("seedling", account, pw)
    adopt(char, account)
    set_rank(char, "owner")
    return account, pw


# --- Cursor: keyset pagination -------------------------------------------------


def test_page_walks_every_hero_once_in_order(client):
    for i in range(5):
        _save(f"hero{i}")
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 2}
        if cursor:
            params["after"] = cursor
        page = client.get("/characters/page", params=params).json()
        seen.extend(h["name"] for h in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == sorted(seen)  # name order
    assert len(seen) == len(set(seen)) == 5  # every hero once, no repeats


def test_page_no_more_flag(client):
    _save("solo")
    page = client.get("/characters/page", params={"limit": 20}).json()
    assert [h["name"] for h in page["items"]] == ["solo"]
    assert page["next_cursor"] is None


def test_page_rejects_bad_size(client):
    assert client.get("/characters/page", params={"limit": 0}).status_code == 422


def test_page_rejects_bad_cursor(client):
    assert client.get("/characters/page", params={"after": "!!!bad"}).status_code == 400


# --- Precondition: optimistic concurrency (ETag / If-Match) --------------------


def test_get_character_returns_an_etag(client):
    _save("vael")
    resp = client.get("/characters/vael")
    assert resp.status_code == 200
    assert resp.headers["ETag"].startswith('"')


def test_unknown_character_is_404(client):
    assert client.get("/characters/nobody").status_code == 404


def test_grant_with_matching_if_match_succeeds(client):
    account, pw = _owner()
    _save("target")
    etag = client.get("/characters/target").headers["ETag"]
    resp = client.post(
        "/admin/grant",
        json={"name": "target", "rank": "wizard"},
        headers={"If-Match": etag},
        auth=(account, pw),
    )
    assert resp.status_code == 200


def test_grant_with_stale_if_match_is_412(client):
    account, pw = _owner()
    _save("target")
    etag = client.get("/characters/target").headers["ETag"]
    # someone else changes the hero -> the read ETag is now stale
    set_rank("target", "wizard")
    resp = client.post(
        "/admin/grant",
        json={"name": "target", "rank": "owner"},
        headers={"If-Match": etag},
        auth=(account, pw),
    )
    assert resp.status_code == 412


def test_grant_without_if_match_still_works(client):
    account, pw = _owner()
    _save("target")
    resp = client.post(
        "/admin/grant",
        json={"name": "target", "rank": "wizard"},
        auth=(account, pw),
    )
    assert resp.status_code == 200  # If-Match is optional (backward compatible)
