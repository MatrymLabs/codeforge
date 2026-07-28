"""Benchmark: the navigation kernel (native Rust vs pure-Python) at world scale.

Evidence for the polyglot claim -- Rust earns its place on bulk graph traversal. Builds a large
directed room-graph and times two workloads on each backend: full-world REACHABILITY (the
connectivity audit) and random PATHFINDING. Prints medians and the speedup. Frameless (perf_counter
+ statistics), no test framework. Run: `python benchmarks/bench_nav.py [n_rooms]`.

If the native `codeforge_nav` kernel is not built, it reports the pure-Python numbers alone (no
speedup line) so the benchmark always runs.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from collections.abc import Callable


def build_edges(n: int, seed: int = 7) -> list[tuple[str, str]]:
    """A large directed graph: a connected spine plus deterministic cross-links (a stand-in for a
    real generated world's exit graph)."""
    rng = random.Random(seed)
    edges: list[tuple[str, str]] = []
    for i in range(n - 1):
        edges.append((f"r{i}", f"r{i + 1}"))
        if i % 3 == 0:
            edges.append((f"r{i}", f"r{rng.randint(0, n - 1)}"))
    return edges


def _median_ms(fn: Callable[[], object], runs: int) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def bench_backend(name: str, graph_factory: Callable[[list[tuple[str, str]]], object], edges, n):
    graph = graph_factory(edges)
    rng = random.Random(99)
    pairs = [(f"r{rng.randint(0, n - 1)}", f"r{rng.randint(0, n - 1)}") for _ in range(2000)]
    reach = _median_ms(lambda: graph.reachable_count("r0"), runs=25)

    def pathfind_batch() -> None:
        for a, b in pairs:
            graph.path(a, b)

    paths = _median_ms(pathfind_batch, runs=5)
    print(f"  {name:<7} reachability: {reach:8.2f} ms   pathfinding(2000): {paths:8.2f} ms")
    return reach, paths


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    edges = build_edges(n)
    print(f"navigation benchmark -- {n:,} rooms, {len(edges):,} exits\n")

    from parts.world.navigation import BACKEND, PyNavGraph

    py = bench_backend("python", PyNavGraph, edges, n)

    try:
        import codeforge_nav
    except ImportError:
        print(
            f"\n(native codeforge_nav not built; active backend = {BACKEND!r}. "
            "Run `maturin develop --release` in native/codeforge_nav for the Rust numbers.)"
        )
        return

    rust = bench_backend("rust", codeforge_nav.NavGraph, edges, n)
    print(
        f"\n  speedup -- reachability: {py[0] / rust[0]:.1f}x   "
        f"pathfinding: {py[1] / rust[1]:.1f}x   (active backend = {BACKEND!r})"
    )


if __name__ == "__main__":
    main()
