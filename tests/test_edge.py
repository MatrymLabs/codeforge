"""Test twin for kernel.edge -- the transparent edge proxy + its launch-time backend selection.

Acceptance: bytes round-trip both directions through the Python reference proxy; many concurrent
clients all get their own byte-clean channel; when the Go binary IS built, it behaves identically
(parity). Refusal: an unreachable backend drops the client cleanly (no hang); with no binary the
launcher reports the pure-Python backend, not a broken one.
"""

from __future__ import annotations

import socket
import subprocess
import threading
import time

import pytest

from kernel.edge import EdgeProxy, edge_backend, resolve_edge_binary


class _EchoBackend:
    """A tiny line server that echoes each line back prefixed 'echo:' -- the far end of the proxy.

    A reply arriving prefixed proves the byte reached the backend AND the backend's reply reached
    the client, i.e. both directions of the proxy work.
    """

    def __init__(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(256)
        self.addr: tuple[str, int] = self._srv.getsockname()[:2]
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        with conn, conn.makefile("rwb") as f:
            for line in f:
                f.write(b"echo:" + line)
                f.flush()

    def stop(self) -> None:
        self._srv.close()


def _round_trip(edge_addr: tuple[str, int], payload: bytes = b"hello\n") -> bytes:
    """Connect to the edge, send one line, return the echoed reply line."""
    with socket.create_connection(edge_addr, timeout=5) as c:
        c.sendall(payload)
        return c.makefile("rb").readline()


# --- the Python reference proxy (always tested) ------------------------------------------------


def test_the_edge_round_trips_bytes_in_both_directions():
    backend = _EchoBackend()
    proxy = EdgeProxy(backend.addr)
    edge_addr = proxy.start(("127.0.0.1", 0))
    try:
        assert _round_trip(edge_addr, b"hello\n") == b"echo:hello\n"
    finally:
        proxy.stop()
        backend.stop()


def test_the_edge_serves_many_concurrent_clients_each_byte_clean():
    backend = _EchoBackend()
    proxy = EdgeProxy(backend.addr)
    edge_addr = proxy.start(("127.0.0.1", 0))
    results: dict[int, bytes] = {}
    lock = threading.Lock()

    def client(i: int) -> None:
        reply = _round_trip(edge_addr, f"c{i}\n".encode())
        with lock:
            results[i] = reply

    threads = [threading.Thread(target=client, args=(i,)) for i in range(50)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        # every client got its OWN reply back, uncrossed (proof the channels don't bleed)
        assert results == {i: f"echo:c{i}\n".encode() for i in range(50)}
    finally:
        proxy.stop()
        backend.stop()


def test_an_unreachable_backend_drops_the_client_instead_of_hanging():
    # Point the edge at a refused port: a connecting client must be closed, not left blocked.
    proxy = EdgeProxy(("127.0.0.1", 1))
    edge_addr = proxy.start(("127.0.0.1", 0))
    try:
        with socket.create_connection(edge_addr, timeout=5) as c:
            c.settimeout(3)
            assert c.recv(1) == b""  # EOF: the edge closed us, it did not hang
    finally:
        proxy.stop()


# --- launch-time selection --------------------------------------------------------------------


def test_edge_backend_reports_python_when_no_binary(tmp_path):
    # A repo root with no built binary must resolve to the Python reference, honestly.
    assert resolve_edge_binary(tmp_path) is None
    assert edge_backend(tmp_path) == "python"


# --- parity: the Go accelerator, only when it is built ----------------------------------------


def test_go_edge_matches_the_python_reference_byte_for_byte():
    binary = resolve_edge_binary()
    if binary is None:
        pytest.skip("Go edge not built (native/edge/codeforge-edge absent) -- fallback path")

    backend = _EchoBackend()
    proc = subprocess.Popen(
        [str(binary), "-listen", "127.0.0.1:0", "-backend", f"{backend.addr[0]}:{backend.addr[1]}"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        ready = proc.stdout.readline().strip()  # "READY 127.0.0.1:NNNNN"
        assert ready.startswith("READY "), f"unexpected readiness line: {ready!r}"
        host, port = ready.split(" ", 1)[1].rsplit(":", 1)
        go_addr = (host, int(port))

        # identical input -> identical output as the Python reference proxy delivers
        assert _round_trip(go_addr, b"hello\n") == b"echo:hello\n"
        assert _round_trip(go_addr, b"forge on\n") == b"echo:forge on\n"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        backend.stop()
        if proc.stdout is not None:
            proc.stdout.close()
        time.sleep(0.05)
