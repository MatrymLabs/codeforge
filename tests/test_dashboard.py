"""Test twin for parts/dashboard.py -- the readiness Lens.

Acceptance: real cards computed from real repo state, an accessible/escaped HTML projection,
a JSON twin that mirrors the page, and both routes live on the FastAPI app. Refusal: a source
that will not load renders an honest red card, never a 500; hostile card text is HTML-escaped.
"""

import pytest
from fastapi.testclient import TestClient

from parts.api import app
from parts.career import load_board, unproven_claims
from parts.dashboard import (
    Card,
    Snapshot,
    build_snapshot,
    render_page,
    status_payload,
)
from parts.hardware import load_catalog

# --- the snapshot: real data, right shape -----------------------------------


def test_snapshot_has_the_four_boards():
    keys = [c.key for c in build_snapshot().cards]
    assert keys == ["career", "qa", "hardware", "perf"]


def test_career_card_matches_the_real_board():
    board = load_board()
    skills = [s for lvl in board["levels"] for s in lvl.get("skills", [])]
    proven = sum(1 for s in skills if s["status"] == "proven")
    card = next(c for c in build_snapshot().cards if c.key == "career")
    assert card.headline == f"{proven}/{len(skills)} proven"
    # VeritasGate: the card's verdict must agree with the real proof-on-disk check.
    assert (card.status == "ok") == (not unproven_claims(board))


def test_hardware_card_counts_the_real_catalog():
    card = next(c for c in build_snapshot().cards if c.key == "hardware")
    assert card.headline == f"{len(load_catalog())} parts"


def test_qa_card_rows_sum_to_the_gate_total():
    card = next(c for c in build_snapshot().cards if c.key == "qa")
    total_in_headline = int(card.headline.split("/")[1].split()[0])
    assert sum(int(v) for _, v in card.rows) == total_in_headline


def test_perf_card_is_honest_about_whether_a_run_exists():
    card = next(c for c in build_snapshot().cards if c.key == "perf")
    # Reports are git-ignored and regenerable: either a filed run (ok) or none yet (info).
    assert card.status in {"ok", "info"}


# --- refusal: a broken source fails honest, not fatal -----------------------


def test_a_broken_source_renders_a_fail_card_not_a_crash(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("registry gone")

    monkeypatch.setattr("parts.qualitygate.gate_all", boom)
    card = next(c for c in build_snapshot().cards if c.key == "qa")
    assert card.status == "fail"
    assert "registry gone" in card.detail


# --- HTML projection: accessible, semantic, escaped -------------------------


def test_page_is_a_semantic_accessible_document():
    page = render_page(build_snapshot())
    assert page.startswith("<!doctype html>")
    for token in ('<html lang="en">', "<header>", "<nav", "<main>", "<footer>", "viewport"):
        assert token in page


def test_page_shows_real_data():
    page = render_page(build_snapshot())
    assert f"{len(load_catalog())} parts" in page


def test_hostile_card_text_is_escaped():
    evil = Snapshot((Card("x", "<script>alert(1)</script>", "ok", "<b>hi</b>", "d"),))
    page = render_page(evil)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


# --- JSON twin mirrors the page ---------------------------------------------


def test_status_payload_mirrors_the_cards():
    snap = build_snapshot()
    payload = status_payload(snap)  # a typed StatusPayload, not a bare dict
    assert payload.engine == "codeforge"
    assert [c.key for c in payload.cards] == [c.key for c in snap.cards]
    hardware = next(c for c in payload.cards if c.key == "hardware")
    assert hardware.headline == next(c.headline for c in snap.cards if c.key == "hardware")


# --- routes: live on the FastAPI app ----------------------------------------


@pytest.fixture()
def client():
    return TestClient(app)


def test_root_serves_the_dashboard_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "CodeForge readiness" in resp.text


def test_status_route_serves_the_json_twin(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["engine"] == "codeforge"
    assert {c["key"] for c in body["cards"]} == {"career", "qa", "hardware", "perf"}


def test_page_wires_htmx_for_progressive_enhancement(client):
    page = client.get("/").text
    assert '<script src="/static/htmx.min.js"' in page  # vendored, same-origin
    assert 'hx-get="/ui/board"' in page  # live board refresh
    # Blueprint links are real <a href> too, so they work without JS (progressive enhancement).
    assert 'href="/ui/blueprint/npc_combat"' in page
    assert 'hx-get="/ui/blueprint/npc_combat"' in page


def test_htmx_asset_is_served_same_origin(client):
    resp = client.get("/static/htmx.min.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert "htmx" in resp.text[:200].lower()


def test_board_fragment_is_swappable_html_not_a_full_page(client):
    resp = client.get("/ui/board")
    assert resp.status_code == 200
    assert 'id="board-grid"' in resp.text
    assert "<!doctype" not in resp.text.lower()  # a fragment, not a whole document


def test_blueprint_fragment_renders_real_content(client):
    resp = client.get("/ui/blueprint/npc_combat")
    assert resp.status_code == 200
    assert "<!doctype" not in resp.text.lower()  # embeddable fragment
    assert "Requirements" in resp.text
    assert "NPCs that fight back" in resp.text


def test_unknown_blueprint_fragment_is_404(client):
    assert client.get("/ui/blueprint/ghost").status_code == 404


def test_status_contract_is_documented_in_openapi(client):
    # The typed response_model means the contract self-documents at /openapi.json (/docs).
    schema = client.get("/openapi.json").json()
    assert "StatusPayload" in schema["components"]["schemas"]
    assert "StatusCard" in schema["components"]["schemas"]
    status_get = schema["paths"]["/api/status"]["get"]
    ref = status_get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/StatusPayload")
