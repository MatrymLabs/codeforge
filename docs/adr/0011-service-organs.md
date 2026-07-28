# ADR-0011: Service organs (out-of-process polyglot components)

Status: Accepted (2026-07-28)

## Context

ADR-0010 admitted polyglot components as **in-process native extensions**: a compiled kernel
(Rust/PyO3, C++/pybind11) swapped in behind a pure-Python fallback **at import time**. That shape
fits CPU work where the win is raw speed on data Python already holds in memory.

It does not fit every language. **Go's signature strength is concurrent I/O** -- thousands of cheap
goroutine-backed connections -- not in-process number crunching (that is already Rust/C++'s lane).
Compiling Go into a `c-shared` `.so` to satisfy the import-time swap would force it through a boundary
that hides the very thing Go is good at, and would demonstrate a *less* honest use of the language.

So we need a second, sibling shape: a polyglot component that runs as its **own process** and is
chosen **at launch**, not at import. This ADR sets that pattern so out-of-process organs follow one
discipline instead of ad-hoc bolt-ons, and keeps the ADR-0010 guarantees that make an accelerator
safe.

## Decision

A **service organ** (an out-of-process, other-language component) is adopted only when it keeps the
ADR-0010 guarantees, re-read for a process boundary:

1. **Python-first with a fallback.** The capability ships as a pure-Python reference first. The
   service is *optional*: when its binary is not built, the game runs on the Python reference and the
   full `make check` is green. Nothing in the game hard-depends on a compiled binary.
2. **A narrow, identical contract.** The service and the Python reference expose the *same*
   behavioural contract (same wire behaviour, same inputs/outputs), so the accelerator is a drop-in
   swap -- chosen at **process launch** (`resolve_*_binary()` -> exec the binary, else run the
   reference) rather than at import.
3. **A parity test.** When the binary is present, a test drives it through the *same* scenarios as the
   Python reference and pins identical behaviour. The accelerator can never silently diverge.
4. **Committed benchmark evidence.** A reproducible benchmark records the measured benefit against the
   Python reference. "It is faster" is measured and dated, with an honest label, never asserted.
5. **Governance.** The technology is recorded in `intake_ledger.toml` and passes `make intake`; its
   toolchain is not added to the runtime dependency set.
6. **Isolation.** Source lives under `native/<name>/`; build artifacts (the compiled binary) are
   git-ignored; the lockfile is committed (or, for a std-lib-only module, `go.mod` alone, noting the
   absence of a `go.sum`); a dedicated, **non-required** CI job builds, unit-tests, and parity-tests
   it, so the main gate never blocks on a cross-language toolchain.

The **only** difference from ADR-0010 is the seam: the swap is at process launch and the contract is
behavioural (wire/round-trip) rather than an imported call signature. Everything that makes an
accelerator *safe* -- fallback, parity, evidence, governance, isolation -- is unchanged.

## First application

`codeforge-edge` (Go, standard library only) -- a **transparent TCP edge gateway**: it accepts client
connections (one goroutine per direction) and byte-proxies each straight to the Python gateway
(`parts/gateway.py`). It never inspects the stream, so telnet/IAC negotiation stays end-to-end and the
edge is a thin, safe pump that raises the connection ceiling without touching game logic.

- **Reference / fallback:** `parts.edge.EdgeProxy` -- the identical proxy, thread-per-connection.
- **Selection:** `parts.edge.run_edge` execs `native/edge/codeforge-edge` when built, else runs the
  reference (`parts.edge.edge_backend()` reports which).
- **Parity:** `tests/test_edge.py::test_go_edge_matches_the_python_reference_byte_for_byte` (runs when
  the binary is built, skips cleanly when it is not).
- **Evidence:** `benchmarks/bench_edge.py` -- concurrent-connection flood, Go goroutines vs Python
  threads. Measured 2026-07-28 on the Pi: ~1.6x at 50 conns rising to **~2.8x at 400** concurrent
  connections (goroutine-per-connection vs thread-per-connection). Honest label: **verified
  improvement** at the connection boundary; not a CPU-compute win.

## Consequences

- **Positive:** Go is used where it genuinely shines (concurrent connection handling) behind the same
  repeatable discipline; the game stays runnable and testable with zero non-Python toolchains; the
  polyglot breadth is real and evidenced. The edge also gives the deployment a natural front door
  that can absorb a connection flood the thread-per-connection gateway would refuse.
- **Costs / risks:** a second build path (Go) and a cross-language CI job; a behavioural parity
  surface to keep in step; the binary must be rebuilt on toolchain bumps. All are bounded by the
  fallback: if the edge is absent or broken, clients connect straight to the Python gateway, and the
  Python reference proxy is always there and always tested.
- **Exit:** delete `native/edge` and the binary branch of `parts.edge.run_edge`; the Python reference
  proxy becomes the sole implementation with no other change.
