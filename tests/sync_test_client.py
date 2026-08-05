"""Synchronous ASGI test client for environments without a working thread portal.

Starlette's TestClient delegates every request through AnyIO's cross-thread blocking portal. The
managed Python image used for this repository can start that portal but cannot wake its event loop,
which makes even a one-route app wait forever. API tests do not need a second server process, so
this adapter runs httpx2's ASGI transport directly in the calling thread.
"""

from __future__ import annotations

from typing import Any

import anyio
import httpx2


class TestClient:
    """Small synchronous facade covering the HTTP API test surface."""

    __test__ = False

    def __init__(self, app: Any, *, base_url: str = "http://testserver", **_: Any) -> None:
        self._app = app
        self._base_url = base_url

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        transport = httpx2.ASGITransport(app=self._app)
        async with httpx2.AsyncClient(transport=transport, base_url=self._base_url) as client:
            return await client.request(method, url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        async def send() -> httpx2.Response:
            return await self._send(method, url, **kwargs)

        return anyio.run(send)

    def get(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("DELETE", url, **kwargs)

    def __enter__(self) -> TestClient:
        return self

    def __exit__(self, *_: Any) -> None:
        return None
