"""CARD: edge -- a transparent TCP edge proxy in front of the gateway.

This is the Python-first reference (ADR-0010) for the polyglot edge organ: a byte-transparent proxy
that accepts client connections and pumps every byte, both directions, straight through to the game
gateway (adapters/gateway.py). It never inspects the stream, so telnet negotiation stays end-to-end
and the edge stays a thin, safe pump: it raises the connection ceiling without touching game logic.

The optional Go accelerator (native/edge, one goroutine per direction instead of a thread) is the
same proxy with a higher concurrency ceiling. The choice happens at LAUNCH, not import (ADR-0011,
the "service organ" pattern): `run_edge` execs the Go binary when it is built, else runs the class
below. When the binary is absent, the game is unaffected -- this reference carries it.

Inputs:  a backend (host, port) to proxy to; a listen (host, port) to accept on.
Outputs: a running proxy; every client byte reaches the backend and every backend byte reaches
         the client, for many concurrent clients, until either side closes that connection.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import socket
import threading
import time
from pathlib import Path

_BUFSIZE = 65536  # copy chunk; matches a comfortable socket read


def _pump(src: socket.socket, dst: socket.socket) -> None:
    """Copy bytes one direction until src closes, then half-close dst's write side so the peer sees
    the EOF (a one-way shutdown -- the other direction may still be flowing)."""
    try:
        while True:
            data = src.recv(_BUFSIZE)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass  # a reset/closed peer is the normal end of a proxied stream
    finally:
        with contextlib.suppress(OSError):
            dst.shutdown(socket.SHUT_WR)


class EdgeProxy:
    """The pure-Python reference edge: thread-per-connection, two pump threads per connection.

    Same contract as the Go accelerator: accept on `listen`, transparently proxy every byte to
    `backend` in both directions, for many concurrent clients. This is what the game runs on when
    the Go binary is not built, and the parity reference the Go edge is measured against.
    """

    def __init__(self, backend: tuple[str, int], *, backlog: int = 128) -> None:
        self._backend = backend
        self._backlog = backlog
        self._srv: socket.socket | None = None
        self._accepting: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self, listen: tuple[str, int]) -> tuple[str, int]:
        """Bind + begin accepting in the background; return the actual bound (host, port).

        Pass port 0 to bind an ephemeral port and read back the real one (used by tests/benchmarks).
        """
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(listen)
        srv.listen(self._backlog)
        self._srv = srv
        self._accepting = threading.Thread(target=self._accept_loop, daemon=True)
        self._accepting.start()
        host, port = srv.getsockname()[:2]
        return host, port

    def _accept_loop(self) -> None:
        assert self._srv is not None
        while not self._stop.is_set():
            try:
                client, _ = self._srv.accept()
            except OSError:
                return  # listener closed: stop cleanly
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket) -> None:
        try:
            backend = socket.create_connection(self._backend)
        except OSError:
            client.close()  # backend down: drop the client cleanly, don't hang
            return
        with client, backend:
            up = threading.Thread(target=_pump, args=(client, backend), daemon=True)
            down = threading.Thread(target=_pump, args=(backend, client), daemon=True)
            up.start()
            down.start()
            up.join()
            down.join()

    def stop(self) -> None:
        """Stop accepting and release the listen socket; in-flight connections drain themselves."""
        self._stop.set()
        if self._srv is not None:
            with contextlib.suppress(OSError):
                self._srv.close()
        if self._accepting is not None:
            self._accepting.join(timeout=2.0)


# --- launch-time backend selection (ADR-0011): the Go edge when built, else this reference ---


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_edge_binary(root: Path | None = None) -> Path | None:
    """The built Go edge binary (native/edge/codeforge-edge) if present + runnable, else None."""
    binary = (root or _repo_root()) / "native" / "edge" / "codeforge-edge"
    return binary if binary.is_file() and os.access(binary, os.X_OK) else None


def edge_backend(root: Path | None = None) -> str:
    """Which edge a launch would use right now: 'go' when the binary is built, else 'python'."""
    return "go" if resolve_edge_binary(root) else "python"


def run_edge(listen: tuple[str, int], backend: tuple[str, int]) -> None:  # pragma: no cover
    """Blocking launcher: exec the Go accelerator when built, else run the Python reference.

    Not unit-tested here (it blocks / execs); the Python proxy and the resolver are covered by
    tests/test_edge.py, and the Go path is exercised by the parity test when the binary is present.
    """
    binary = resolve_edge_binary()
    if binary is not None:
        # The exec target is our own resolved in-tree binary (native/edge), not untrusted input;
        # the args are the operator's chosen listen/backend addresses.
        os.execv(  # nosec B606  # noqa: S606
            str(binary),
            [
                str(binary),
                "-listen",
                f"{listen[0]}:{listen[1]}",
                "-backend",
                f"{backend[0]}:{backend[1]}",
            ],
        )
    proxy = EdgeProxy(backend)
    host, port = proxy.start(listen)
    print(f"edge (python): listening on {host}:{port} -> {backend[0]}:{backend[1]}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        proxy.stop()


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="CodeForge edge proxy (Go accelerator when built)."
    )
    parser.add_argument("--listen", default="0.0.0.0:4001", help="host:port to accept clients on")
    parser.add_argument("--backend", default="127.0.0.1:4000", help="gateway host:port to proxy to")
    args = parser.parse_args(argv)

    def split(hp: str) -> tuple[str, int]:
        host, port = hp.rsplit(":", 1)
        return host, int(port)

    run_edge(split(args.listen), split(args.backend))


if __name__ == "__main__":  # pragma: no cover
    main()
