"""E2E harness: run the real FastAPI app in a thread and drive it with a real browser.

These tests live OUTSIDE `tests/` (not in pytest `testpaths`), so `make check` never collects
them and the main suite stays fast and browser-free. Run them with `make e2e`.
"""

from __future__ import annotations

import os
import socket
import threading
import time

import pytest

# Keep any real database out of the way; the dashboard endpoints under test do not touch it.
os.environ.setdefault("CODEFORGE_DB", "/tmp/codeforge_e2e.db")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


@pytest.fixture(scope="session")
def base_url():
    """Serve parts.api.app on a background uvicorn thread; yield its URL."""
    import uvicorn

    from parts.api import app

    class _ThreadedServer(uvicorn.Server):
        def install_signal_handlers(self) -> None:  # don't hijack signals off the main thread
            pass

    port = _free_port()
    server = _ThreadedServer(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("uvicorn did not start for the E2E run")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def _browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def page(_browser):
    page = _browser.new_page()
    yield page
    page.close()
