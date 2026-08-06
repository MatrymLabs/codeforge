"""Test twin for adapters/api.py -- the HTTP window, via TestClient."""

import pytest

from adapters.api import _get_login_guard, app
from kernel.login_guard import LoginGuard
from kernel.seedlab.deployment import DeploymentProfile, LocalDeploymentController
from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.platform_proof import run_first_platform_proof
from kernel.seedlab.workshop_services import CreatorWorkshopService
from kernel.world.accounts import adopt, register
from kernel.world.characters import save_character, set_rank
from kernel.world.session import SESSIONS, Session
from tests.sync_test_client import TestClient


@pytest.fixture(autouse=True)
def fresh_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


@pytest.fixture(autouse=True)
def fresh_login_guard():
    # One throttle instance per test (shared across that test's requests), so the 5-attempt burst
    # is real within a test but never leaks across tests.
    guard = LoginGuard()

    async def override_guard() -> LoginGuard:
        return guard

    app.dependency_overrides[_get_login_guard] = override_guard
    yield
    app.dependency_overrides.clear()


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


def test_platform_status_exposes_the_shared_runtime_contract(client):
    response = client.get("/api/platform/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["seed"] == "first-forge"  # direct API import preserves library compatibility
    names = {component["name"] for component in payload["components"]}
    assert {"engine", "seed-runtime", "hardware-store", "rnd", "creator-workshop"} <= names


def test_seedlab_workspace_endpoint_exposes_authoritative_deployment(client, tmp_path, monkeypatch):
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "API Workspace", "josh", "an API workspace", seed_id="seed-api"
    )
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "app.txt").write_text("healthy", encoding="utf-8")
    LocalDeploymentController(home / "deployments", id_minter=iter(["deploy-api"]).__next__).deploy(
        DeploymentProfile("local-api", "seed-api", "artifact-api", str(artifact))
    )
    CreatorWorkshopService.durable(home / "workshop").create_draft(
        "draft-api", "seed-api", "josh", {"command": "inspect"}
    )

    response = client.get("/api/seedlab/workspaces/seed-api")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project"]["deployment"]["status"] == "deployed"
    evidence = next(
        package["payload"]
        for package in payload["packages"]
        if package["package"] == "Engineering.Evidence"
    )
    assert evidence["lifecycle"]["drafts"][0]["draft_id"] == "draft-api"
    assert evidence["lifecycle"]["health"][0]["run_id"] == "deploy-api"


def test_seedlab_connect_and_disconnect_are_authenticated_authoritative_mutations(
    client, tmp_path, monkeypatch
):
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    source = tmp_path / "connected-project"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        "[project]\nname = 'connected-project'\n", encoding="utf-8"
    )
    account, password = _owner_account(account="seed-owner", pw="swordfish")
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "API Connect",
        account,
        "authenticated connector mutation",
        seed_id="seed-connect-api",
    )

    denied = client.post(
        "/api/seedlab/workspaces/seed-connect-api/connect",
        json={"path": str(source)},
    )
    assert denied.status_code == 401

    connected = client.post(
        "/api/seedlab/workspaces/seed-connect-api/connect",
        json={"path": str(source)},
        auth=(account, password),
    )
    assert connected.status_code == 200
    payload = connected.json()
    assert payload["project_state"]["connectors"]

    disconnected = client.post(
        "/api/seedlab/workspaces/seed-connect-api/disconnect",
        json={"source_id": source.name},
        auth=(account, password),
    )
    assert disconnected.status_code == 200
    assert disconnected.json()["project_state"]["connectors"] == []


def test_seedlab_creator_draft_mutations_are_owner_scoped_and_projected(
    client, tmp_path, monkeypatch
):
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    account, password = _owner_account(account="draft-owner", pw="swordfish")
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Draft API", account, "authenticated draft mutation", seed_id="seed-draft-api"
    )

    denied = client.post(
        "/api/seedlab/workspaces/seed-draft-api/drafts",
        json={"draft_id": "draft-api", "payload": {"kind": "item"}},
    )
    assert denied.status_code == 401

    created = client.post(
        "/api/seedlab/workspaces/seed-draft-api/drafts",
        json={"draft_id": "draft-api", "payload": {"kind": "item"}},
        auth=(account, password),
    )
    assert created.status_code == 200
    lifecycle = next(
        package["payload"]["lifecycle"]
        for package in created.json()["packages"]
        if package["package"] == "Engineering.Evidence"
    )
    assert lifecycle["drafts"][0]["draft_id"] == "draft-api"

    edited = client.post(
        "/api/seedlab/workspaces/seed-draft-api/drafts/draft-api/edit",
        json={"changes": {"label": "A governed item"}},
        auth=(account, password),
    )
    assert edited.status_code == 200
    draft = next(
        record
        for package in edited.json()["packages"]
        if package["package"] == "Engineering.Evidence"
        for record in package["payload"]["lifecycle"]["drafts"]
    )
    assert draft["payload"]["label"] == "A governed item"

    transitioned = client.post(
        "/api/seedlab/workspaces/seed-draft-api/drafts/draft-api/transition",
        json={"target": "validated"},
        auth=(account, password),
    )
    assert transitioned.status_code == 200
    draft = next(
        record
        for package in transitioned.json()["packages"]
        if package["package"] == "Engineering.Evidence"
        for record in package["payload"]["lifecycle"]["drafts"]
    )
    assert draft["status"] == "validated"


def test_seedlab_task_creation_is_owner_authenticated_idempotent_and_projected(
    client, tmp_path, monkeypatch
):
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    account, password = _owner_account(account="task-owner", pw="swordfish")
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Task API", account, "authenticated implementation task", seed_id="seed-task-api"
    )
    body = {
        "task_id": "observation-room-format",
        "title": "Improve room presentation",
        "description": "Separate room description, occupants, and exits.",
        "source_proposal": "codeforge-observation-room.json",
        "evidence_ids": ["INS-003", "OBS-001"],
    }

    assert client.post("/api/seedlab/workspaces/seed-task-api/tasks", json=body).status_code == 401

    created = client.post(
        "/api/seedlab/workspaces/seed-task-api/tasks",
        json=body,
        auth=(account, password),
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["task"]["status"] == "ready"
    assert payload["task"]["owner_id"] == account
    assert payload["workspace"]["project"]["tasks"] == [payload["task"]]

    repeated = client.post(
        "/api/seedlab/workspaces/seed-task-api/tasks",
        json=body,
        auth=(account, password),
    )
    assert repeated.status_code == 200
    assert repeated.json()["task"] == payload["task"]

    changed = dict(body, title="A different task")
    conflict = client.post(
        "/api/seedlab/workspaces/seed-task-api/tasks",
        json=changed,
        auth=(account, password),
    )
    assert conflict.status_code == 400
    assert "different content" in conflict.json()["detail"]

    projected = client.get(
        "/api/seedlab/workspaces/seed-task-api", auth=(account, password)
    )
    assert projected.status_code == 200
    assert projected.json()["project"]["tasks"] == [payload["task"]]


def test_platform_proof_endpoint_requires_owner_and_replays_exact_evidence(
    client, tmp_path, monkeypatch
):
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    proof = run_first_platform_proof(
        home / "proof",
        owner="josh",
        id_minter=lambda _name: "seed-api-proof",
    )
    account, password = _owner_account()

    assert client.get(f"/api/seedlab/proofs/{proof.seed_id}").status_code == 401
    response = client.get(
        f"/api/seedlab/proofs/{proof.seed_id}",
        auth=(account, password),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "seedlab.platform-proof/1"
    assert payload["seed_id"] == proof.seed_id
    assert len(payload["semantic_events"]) == 7
    assert payload["deployment"]["status"] == "deployed"
    assert payload["failed_deployment"]["status"] == "failed"
    assert payload["recovered_deployment"]["status"] == "deployed"


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
    assert npc["status"] == "validated"  # the feature is fully built in kernel/world/combat.py
    assert npc["requirement_count"] >= 1


def test_blueprints_contract_is_documented_in_openapi(client):
    schema = client.get("/openapi.json").json()
    assert "BlueprintSummary" in schema["components"]["schemas"]


def test_creator_workshop_catalog_comes_from_the_authoritative_hardware_store(client):
    response = client.get("/api/creator-workshop/catalog")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "creator-workshop"
    event_ledger = next(part for part in payload["parts"] if part["id"] == "event-ledger")
    assert event_ledger["license"] == "MIT"
    assert event_ledger["source_status"] == "original"


def test_grant_refuses_the_unauthenticated(client):
    _owner_account()
    response = client.post("/admin/grant", json={"name": "matrym", "rank": "wizard"})
    assert response.status_code == 401
    response = client.post(
        "/admin/grant", json={"name": "matrym", "rank": "wizard"}, auth=("matlabs", "wrong")
    )
    assert response.status_code == 401


def test_get_login_guard_returns_the_shared_throttle():
    """The production seam hands back the one shared guard (tests override it for isolation)."""
    from adapters.api import _login_guard, get_login_guard

    assert get_login_guard() is _login_guard


def test_admin_auth_is_rate_limited_against_brute_force(client):
    """The HTTP admin surface caps guessing the same way the telnet gateway does: a 5-attempt
    burst, then 429 - so the owner password can't be brute-forced one pbkdf2 at a time."""
    _owner_account()
    body = {"name": "matrym", "rank": "wizard"}
    for _ in range(5):  # the burst: five wrong guesses, each a normal 401
        assert client.post("/admin/grant", json=body, auth=("matlabs", "wrong")).status_code == 401
    blocked = client.post("/admin/grant", json=body, auth=("matlabs", "wrong"))  # the sixth
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


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
