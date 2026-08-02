"""Consumer-driven contract tests: the client's expected API shapes, verified against the LIVE api.

This is the real CONSUMER of kernel/shelf/contract.py (MOD-05.015). Each contract is what a client
(the Master Client) reads from a codeforge endpoint; the provider-side test fetches the real
response via TestClient and fails if a field the client depends on was dropped or retyped -- a
breaking API change caught in CI, not at runtime. Extra provider fields are tolerated (tolerant
reader).
"""

import pytest
from fastapi.testclient import TestClient

from kernel.shelf.contract import Contract, ContractRegistry, Field, verify_all
from parts.api import app

# The shapes the Master Client depends on (declared by the consumer, verified by the provider).
BLUEPRINT_ITEM = Contract(
    "GET /api/blueprints item",
    "master-client",
    (
        Field("blueprint_id", str),
        Field("title", str),
        Field("intent", str),
        Field("status", str),
        Field("requirement_count", int),
    ),
)
ROOM_ITEM = Contract(
    "GET /world/rooms item",
    "master-client",
    (Field("label", str), Field("name", str)),
)


@pytest.fixture()
def client():
    return TestClient(app)


def _assert_every_item_satisfies(registry: ContractRegistry, name: str, items: list) -> None:
    assert items, f"{name}: expected a non-empty list to verify the contract against"
    for item in items:
        violations = verify_all(registry, name, item)
        assert violations == [], f"{name} broke the master-client contract: {violations}"


def test_blueprint_list_satisfies_the_client_contract(client):
    registry = ContractRegistry()
    registry.register(BLUEPRINT_ITEM)
    resp = client.get("/api/blueprints")
    assert resp.status_code == 200
    _assert_every_item_satisfies(registry, "GET /api/blueprints item", resp.json())


def test_rooms_list_satisfies_the_client_contract(client):
    registry = ContractRegistry()
    registry.register(ROOM_ITEM)
    resp = client.get("/world/rooms")
    assert resp.status_code == 200
    _assert_every_item_satisfies(registry, "GET /world/rooms item", resp.json())
