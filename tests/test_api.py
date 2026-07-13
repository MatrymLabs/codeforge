"""Test twin for parts/api.py -- the HTTP window, via TestClient."""

import pytest
from fastapi.testclient import TestClient

from parts.accounts import adopt, register
from parts.api import app
from parts.characters import save_character, set_rank
from parts.session import SESSIONS, Session


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _owner_account(char="matrym", account="matlabs", pw="swordfish"):
    hero = Session(player_id=char, location="courtyard", named=True, account=account, level=2)
    SESSIONS[char] = hero
    save_character(hero)
    SESSIONS.clear()
    register("seedling", account, pw)
    adopt(char, account)
    set_rank(char, "owner")
    return account, pw


def test_health_answers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_characters_reads_the_canonical_table(client):
    _owner_account()
    heroes = client.get("/characters").json()
    names = {h["name"] for h in heroes}
    assert "matrym" in names
    matrym = next(h for h in heroes if h["name"] == "matrym")
    assert matrym["level"] == 2
    assert matrym["rank"] == "owner"


def test_rooms_expose_the_seed_graph(client):
    rooms = client.get("/world/rooms").json()
    labels = {r["label"] for r in rooms}
    assert "forge" in labels
    forge = next(r for r in rooms if r["label"] == "forge")
    assert forge["exits"]["north"] == "courtyard"


def test_blueprints_endpoint_summarizes_filed_plans(client):
    resp = client.get("/api/blueprints")
    assert resp.status_code == 200
    plans = resp.json()
    npc = next(b for b in plans if b["blueprint_id"] == "npc_combat")
    assert npc["title"] == "NPCs that fight back"
    assert npc["status"] == "validated"  # the feature is fully built in parts/combat.py
    assert npc["requirement_count"] >= 1


def test_blueprints_contract_is_documented_in_openapi(client):
    schema = client.get("/openapi.json").json()
    assert "BlueprintSummary" in schema["components"]["schemas"]


def test_grant_refuses_the_unauthenticated(client):
    _owner_account()
    response = client.post("/admin/grant", json={"name": "matrym", "rank": "wizard"})
    assert response.status_code == 401
    response = client.post(
        "/admin/grant", json={"name": "matrym", "rank": "wizard"}, auth=("matlabs", "wrong")
    )
    assert response.status_code == 401


def test_grant_with_owner_credentials_changes_rank(client):
    account, pw = _owner_account()
    hero = Session(player_id="apprentice", named=True)
    SESSIONS["apprentice"] = hero
    save_character(hero)
    SESSIONS.clear()
    response = client.post(
        "/admin/grant", json={"name": "apprentice", "rank": "wizard"}, auth=(account, pw)
    )
    assert response.status_code == 200
    assert "wizard" in response.json()["result"]


def test_grant_validates_rank_and_target(client):
    account, pw = _owner_account()
    assert (
        client.post(
            "/admin/grant", json={"name": "matrym", "rank": "demigod"}, auth=(account, pw)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/admin/grant", json={"name": "ghost", "rank": "wizard"}, auth=(account, pw)
        ).status_code
        == 404
    )
