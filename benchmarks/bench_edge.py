"""Benchmark: the edge proxy (Go goroutines vs Python threads) under a connection flood.

Evidence for the polyglot claim -- Go earns its place at the connection boundary. The Python
gateway is thread-per-connection with a ceiling (MAX_CONNECTIONS = 128); the edge's job is to hold
the flood of concurrent sockets. So this measures the RIGHT thing for Go: not CPU, but how each
backend copes when many clients connect, round-trip, and disconnect at once.

For a concurrency level N it opens N simultaneous connections through the edge to a local echo
backend, each sending one line and reading the reply, and records the wall time to clear all N.
Frameless (perf_counter + statistics). Run: `python benchmarks/bench_edge.py [max_conns]`.

If the Go binary (native/edge/codeforge-edge) is not built it reports the Python numbers alone (no
speedup line), so the benchmark always runs.
"""

from __future__ import annotations

import socket
import statistics
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from kernel.edge import EdgeProxy, resolve_edge_binary


class _EchoBackend:
    """Local line-echo server: the far end every proxied connection talks to."""

    def __init__(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1024)
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


def _flood(edge_addr: tuple[str, int], n: int) -> None:
    """Open n connections at once; each sends a line and reads its reply. Raises on any failure."""
    errors: list[str] = []

    def one(i: int) -> None:
        try:
            with socket.create_connection(edge_addr, timeout=10) as c:
                c.sendall(f"c{i}\n".encode())
                if c.makefile("rb").readline() != f"echo:c{i}\n".encode():
                    errors.append(f"conn {i}: bad reply")
        except OSError as exc:
            errors.append(f"conn {i}: {exc}")

    threads = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError(f"{len(errors)}/{n} connections failed (e.g. {errors[0]})")


def _median_ms(fn: Callable[[], None], runs: int) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def bench_python(backend: tuple[str, int], levels: list[int]) -> dict[int, float]:
    proxy = EdgeProxy(backend, backlog=1024)
    edge_addr = proxy.start(("127.0.0.1", 0))
    try:
        return {n: _median_ms(lambda n=n: _flood(edge_addr, n), runs=5) for n in levels}
    finally:
        proxy.stop()


def bench_go(binary: str, backend: tuple[str, int], levels: list[int]) -> dict[int, float]:
    proc = subprocess.Popen(  # noqa: S603
        [binary, "-listen", "127.0.0.1:0", "-backend", f"{backend[0]}:{backend[1]}"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    ready = proc.stdout.readline().strip()  # "READY host:port"
    host, port = ready.split(" ", 1)[1].rsplit(":", 1)
    edge_addr = (host, int(port))
    try:
        return {n: _median_ms(lambda n=n: _flood(edge_addr, n), runs=5) for n in levels}
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def main() -> None:
    max_conns = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    levels = [n for n in (50, 100, 200, 400, 800) if n <= max_conns]
    backend = _EchoBackend()

    print(f"edge benchmark -- concurrent connections through the proxy (up to {max_conns})\n")
    py = bench_python(backend.addr, levels)
    binary = resolve_edge_binary()
    go = bench_go(str(binary), backend.addr, levels) if binary else None

    header = f"  {'conns':>6}   {'python(ms)':>12}"
    header += f"   {'go(ms)':>10}   {'speedup':>8}" if go else ""
    print(header)
    for n in levels:
        line = f"  {n:>6}   {py[n]:>12.2f}"
        if go:
            ratio = py[n] / go[n] if go[n] else float("inf")
            line += f"   {go[n]:>10.2f}   {ratio:>7.2f}x"
        print(line)

    backend.stop()
    if not go:
        print("\n(native Go edge not built -- Python reference numbers only)")
    print("\nHigher connection counts are where goroutine-per-connection pulls ahead of")
    print("thread-per-connection: Python pays ~8KB+ of stack per OS thread, Go a few KB each.")


if __name__ == "__main__":
    main()
