# ADR-0010: Polyglot native extensions behind a Python-first fallback

Status: Accepted (2026-07-28)

## Context

CodeForge's professional thesis is broadening from "a Python MUD engine" to a **polyglot
assimilation platform**: the demonstrated ability to reach for the right language at each boundary
and integrate them cleanly. The architecture modernization review
(`docs/architecture_modernization_review_2026-07.md`) established that Python is the correct core for
the game domain (microsecond hot paths, no CPU bottleneck) and that other languages should enter
**only at measured boundaries, behind narrow interfaces, with evidence**. This ADR sets the pattern
for how a non-Python component is admitted, so every future organ (Rust, Go, C, C++/QML, ...) follows
one disciplined shape rather than ad-hoc bolt-ons.

## Decision

A native (or other-language) component is adopted only when it satisfies **all** of:

1. **Python-first with a fallback.** The capability ships as a pure-Python reference first. The
   native accelerator is *optional*: when it is not built, the game runs on the Python fallback and
   the full `make check` is green. Nothing in the game hard-depends on a compiled artifact.
2. **A narrow, identical interface.** The native and Python implementations expose the *same* API,
   so the accelerator is a drop-in swap chosen at import time (`try: import <native>` else fallback).
3. **A parity test.** When the native module is present, a test pins it to byte-identical behaviour
   against the Python reference. The accelerator can never silently diverge.
4. **Committed benchmark evidence.** A reproducible benchmark records the speedup (or other measured
   benefit). "It is faster" is not asserted; it is measured and dated.
5. **Governance.** The technology is recorded in `intake_ledger.toml` (purpose, boundary, security,
   license, testing/failure/upgrade/removal) and passes `make intake`; build tooling is not added to
   the runtime dependency set.
6. **Isolation.** Source lives under `native/<crate>/`; build artifacts are git-ignored; the lockfile
   (`Cargo.lock`) is committed; a dedicated, non-required CI job builds and parity-tests it, so the
   main gate never blocks on a cross-language toolchain.

## First application

`codeforge_nav` (Rust via PyO3/maturin) — the world-navigation kernel (`NavGraph`: shortest room
paths + reachability). Fallback: `parts.world.navigation.PyNavGraph`. Parity: `tests/test_navigation.py`.
Evidence: `benchmarks/bench_nav.py` (measured ~30x reachability / ~17x pathfinding at scale). Wired
into the `route <room>` command via `parts.world.travel`.

## Consequences

- **Positive:** each language is used where it genuinely helps, integrated behind one repeatable
  discipline; the game stays runnable and testable with zero non-Python toolchains; the polyglot
  breadth is real and evidenced, not cosmetic; and the "assimilation" thesis is demonstrated, not
  claimed.
- **Costs / risks:** a second build path (maturin) and a cross-language CI job; a parity surface to
  maintain; the accelerator must be rebuilt on interpreter/toolchain bumps. All are bounded by the
  fallback: if any native path breaks, the pure-Python implementation carries the game unaffected.
- **Exit:** delete the crate and its opportunistic import; the Python fallback becomes the sole
  implementation with no other change.
