# Native-organ benchmark evidence (2026-07-28)

*Recorded evidence for the polyglot accelerator claim, closing the gap the 2026-07-28 knowledge
convergence audit flagged: the native organs' speedups were computed at runtime by `benchmarks/
bench_*.py` but never written down to the optimization-ethos standard (baseline, change, first-call
overhead, parity, honest label). This is that record.*

Measured on the Raspberry Pi 5 ("skynet", aarch64, Python 3.13), release build via maturin, at the
commit that introduced this file. Reproduce with `python benchmarks/bench_nav.py 30000`.

## Headline organ: the Rust navigation kernel (`native/codeforge_nav`, PyO3)

Workload: a directed room-graph, two operations, median of repeated runs (`perf_counter` +
`statistics`, frameless). Measured at two scales to show the speedup is stable, not cherry-picked:

| Scale | Operation | Pure Python | Rust kernel | Speedup | Label |
|-------|-----------|-------------|-------------|---------|-------|
| 30,000 rooms | Full-world reachability | 15.55 ms | 0.96 ms | **16.3x** | verified improvement |
| 30,000 rooms | Pathfinding, 2,000 pairs | 15,381.97 ms | 1,363.22 ms | **11.3x** | verified improvement |
| 50,000 rooms | Full-world reachability | 33.20 ms | 2.29 ms | **14.5x** | verified improvement |
| 50,000 rooms | Pathfinding, 2,000 pairs | 31,603.22 ms | 2,627.74 ms | **12.0x** | verified improvement |

The Rust kernel holds a roughly **11x to 16x** advantage across scale (reachability ~14-16x,
pathfinding ~11-12x). It does not reach the higher multiples toy-kernel studies report, and it does
not need to; this is the real, stable, measured figure. **This report is the single source of truth
for the number; docs cite it rather than hardcoding a multiple that drifts.**

**First-call / FFI overhead (the honest tradeoff).** Cold import of the compiled kernel costs
**0.693 ms** in a fresh process; per-call FFI overhead is in the microseconds. This is the number
that justifies Rust over a JIT: it is roughly three orders of magnitude below Numba's typical
first-call JIT warm-up (~0.3 s), so a hot path that is not kept warm pays almost nothing to reach the
compiled code (see the language-selection record in ADR-0010).

**Parity (correctness before speed).** `tests/test_navigation.py` pins the Rust kernel to
byte-identical results with the pure-Python reference (`test_backend_is_reported_and_usable` plus the
per-operation twins); when the kernel is not built, that parity test skips and the pure-Python
fallback carries the world (ADR-0010: Python-first, native-optional). Speed is never traded for a
different answer.

**Honesty note.** The literature's Rust-from-Python studies report 100x to 300x on toy kernels (dot
products, dense matvec). Our real navigation kernel returns 11x to 16x on a real world graph. The
smaller multiple is the *more* credible one: a real kernel has less headroom than a synthetic
best-case, and this number is measured on the actual workload the engine runs, not a microbenchmark
chosen to flatter the result. We state the real figure, not the literature's toy-kernel ceiling.

## The other organs

Each accelerator ships its own runnable benchmark; this record focuses on the navigation kernel
because it is the headline claim. The rest are reproducible on demand and follow the same
Python-first-fallback, parity-pinned pattern:

| Organ | Language | Benchmark | Role |
|-------|----------|-----------|------|
| edge session gateway | Go | `benchmarks/bench_edge.py` | connection fan-out |
| character analytics | SQL | `benchmarks/bench_analytics.py` | set-shaped reports (parity vs Python reference) |
| telemetry frame codec | protobuf/C | `benchmarks/bench_telemetry.py` | wire encode/decode |
| text matcher | C | `benchmarks/bench_textmatch.py` | command/keyword matching |

Each should grow its own recorded row here as it is benchmarked; this file is the durable home for
that evidence rather than leaving the numbers to live only in transient stdout.

## Verdict

The Rust navigation kernel is a **verified improvement** on bulk graph traversal (11x to 16x at world
scale), it preserves correctness (parity-pinned), and its first-call overhead is negligible next to
the JIT alternative. The polyglot claim now has a recorded artifact behind it, not just runtime
output.
