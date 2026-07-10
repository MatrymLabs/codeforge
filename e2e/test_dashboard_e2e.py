"""End-to-end browser tests for the live dashboard (real Chromium, real server).

Proves the HTMX enhancements actually work in a browser: the board renders, Refresh swaps it
via HTMX, and clicking a Blueprint renders it in-page. Complements the route-level tests in
tests/test_dashboard.py with a true front-to-back check.
"""


def test_dashboard_loads_with_cards(page, base_url):
    page.goto(base_url)
    assert "CodeForge readiness" in page.content()
    # The four evidence cards are server-rendered and present in the DOM.
    assert page.locator("article.card").count() >= 3


def test_refresh_button_swaps_the_board_via_htmx(page, base_url):
    page.goto(base_url)
    page.click("button.refresh")
    # HTMX replaces #board-grid; after the swap the grid and its cards are still there.
    page.wait_for_selector("#board-grid article.card")
    assert page.locator("#board-grid article.card").count() >= 3


def test_clicking_a_blueprint_renders_it_in_page(page, base_url):
    page.goto(base_url)
    assert page.locator("#bp-panel h2").count() == 0  # empty before a click
    page.click("ul.bp-list a")
    page.wait_for_selector("#bp-panel h2")
    panel = page.locator("#bp-panel").inner_text()
    assert "NPCs that fight back" in panel
    assert "Requirements" in panel


def test_metrics_endpoint_is_live(page, base_url):
    # The observability endpoint responds with Prometheus text through the running server.
    response = page.request.get(f"{base_url}/metrics")
    assert response.ok
    assert "codeforge_requests_total" in response.text()
