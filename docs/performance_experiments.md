# Performance experiment cards

One card per proposed optimization. **None are executed yet** - this is the measurement
foundation. Each is a hypothesis to be run later on a branch, with a before/after comparison,
a correctness proof of output equivalence, and a rollback. All three targets are Level-1
(Python/architecture cleanup: caching, lazy import) - **none justify Rust, a compiler, or a
GPU**, which matches the research (see `performance_research_map.md`).

Baselines measured 2026-07-11 on a Raspberry Pi 5 (aarch64, Python 3.13.5, 4 cores, 15 GiB),
commit de0f8a5. Reproduce with `python -m benchmarks.perf_journeys`.

---

## EXP-001 - Cache the parsed Hardware Store catalog

- **Repository Area:** F (Hardware Store / registry). `parts/workshop.py:reuse_search`, `parts/hardware.py:load_catalog`.
- **Observed Problem:** `reuse_search` calls `load_catalog()` on every search, which re-reads and re-parses `catalog/parts.yaml` with `yaml.safe_load` each call.
- **Evidence of Problem / Profiling:** cProfile of 100 `reuse_search("engine")` calls = 13.97 s, of which **13.82 s (99%) is `yaml.safe_load`** (`reports/performance/profiles/catalog_search.txt`).
- **Current Baseline:** catalog search median **39 ms**, p95 67 ms (the catalog never changes within a process).
- **Hypothesis:** memoizing the parsed catalog (parse once per process, or per file-mtime) removes the repeated parse; search drops toward the pure substring cost (< 1 ms).
- **Proposed Change:** cache `load_catalog()` (e.g. `functools.lru_cache` keyed on path+mtime, or a module-level parsed cache), preserving the loud-fail-on-bad-row behavior.
- **Alternative Options:** parse at import (like `parts/jobs.py` loads `JOBS`); or an mtime-guarded reload for hot-edit during dev.
- **Correctness Tests:** assert cached result == freshly parsed result; the existing `test_hardware.py` VeritasGate (every part maps to a domain) still passes; a bad row still fails loud.
- **Benchmark Workload:** `reuse_search` and `find_part` over the shipped catalog. Input sizes: current catalog, plus a synthetic large catalog. Warmup 200, reps 2000.
- **Metrics:** median/p95 latency, `yaml.safe_load` call count, peak memory.
- **Expected Benefit:** ~40x on catalog/registry search and every `find_part` caller (career board, `catalog`, `reuse`). **Potential Harm:** stale catalog after a live file edit (mitigated by mtime guard).
- **Compatibility / Security Risk:** none (read-only, same data). **Maintenance Cost:** low.
- **Rollback:** revert the cache block.
- **Result / Decision:** **VERIFIED IMPROVEMENT (executed 2026-07-11).** catalog search median
  **39 ms -> 91.8 us (~426x)**, p95 67 ms -> 0.12 ms; cProfile confirms `yaml.safe_load` left
  the hot path. Correctness proven: `cached == fresh`, an on-disk edit (mtime) invalidates, a
  bad edit fails loud and is never cached. Full suite passed (+4 cache tests) with branch
  coverage green. No behavior change, no new dependency. Regression guard: the parse-once and
  mtime-invalidation tests in `test_hardware.py`. **Reuse (SHIPPED 2026-07-11):** the mtime-guarded
  loader cache was promoted to a shared part, `parts/loader_cache.py` (its own test twin), and now
  serves the catalog AND the classification registry (see EXP-002). One solution, three customers.
  Workload class: serialization/I-O-bound. Level 1.

---

## EXP-002 - Reduce the QA-gate filesystem `stat` storm

- **Repository Area:** J (QA/Veritas) + F. `parts/qualitygate.py:gate_all` / `run_gate` / `exists`.
- **Observed Problem:** `qa gate all` grades every filed object by checking proof-path existence, issuing hundreds of `pathlib.Path.exists()` -> `os.stat` calls per invocation.
- **Evidence / Profiling:** cProfile of 20 `render_gate_all()` calls = 0.453 s with **8,920 `posix.stat` calls (~446 per gate run)** dominating (`reports/performance/profiles/qa_gate_all.txt`).
- **Current Baseline:** `qa gate all` median **8.2 ms**, p95 10.1 ms.
- **Hypothesis:** many paths are re-`stat`ed within one run (and across runs of unchanged artifacts); caching existence within a run - or memoizing the gate verdict for unchanged files by mtime - cuts the stat count.
- **Proposed Change:** measure the duplicate-stat ratio first; then cache existence per `gate_all` call, or per-file mtime across runs. **Do not** change any grading behavior.
- **Alternative Options:** batch existence checks via a single directory scan; precompute a path set.
- **Correctness Tests:** the full grade output is byte-identical before/after; `test_qualitygate.py` passes.
- **Benchmark Workload:** `render_gate_all` over the shipped registry; also a synthetic 10x registry.
- **Metrics:** median latency, `stat` call count, I/O counts.
- **Expected Benefit:** proportional to the duplicate-stat ratio (to be measured). **Potential Harm:** a cached verdict could miss a mid-run file change (dev-only concern).
- **Compatibility / Security Risk:** none. **Maintenance Cost:** low-medium.
- **Rollback:** revert the cache.
- **Result / Decision:** **VERIFIED IMPROVEMENT (executed 2026-07-11, with EXP-001 reuse).** A
  per-audit existence memo shared across all records (and across QG02/QG03/QG05, which re-checked
  file+tests) cut `exists()` stat calls **446 -> 139 per cold `gate_all`** (one per unique proof
  path, zero duplicates) and `qa gate all` median **9.4 ms -> 2.91 ms (~3.2x)**. In the SAME change,
  the registry adopted the shared mtime-guarded loader cache (the EXP-001 "reuse"): repeated
  `load_collective` now parses each `designations/*.json` once (**12 -> 4** `_parse_designations`
  calls over 3 audits). Output byte-identical; full suite 700 passed, 93.59%. Regression guard:
  `test_run_gate_honors_the_shared_stat_cache`, `test_gate_all_stats_each_path_once`,
  `test_designations_are_parsed_once_and_cached`. Workload class: **I/O-bound**. Level 2 (remove
  duplicate work).

---

## EXP-003 - Lazy-load SQLAlchemy to cut cold startup

- **Repository Area:** A (server/runtime). `parts/db.py` (imports `sqlalchemy` at module import), reached eagerly via `forge.py -> parts.accounts -> parts.characters -> parts.db`.
- **Observed Problem:** `import forge` eagerly imports the whole persistence stack even for DB-free paths (help, look, a benchmark).
- **Evidence / Profiling:** `python -X importtime -c "import forge"` -> forge 647 ms cumulative, of which **SQLAlchemy ~412 ms** (`reports/performance/profiles/startup_importtime.txt`). Import peak memory 25.6 MB (tracemalloc).
- **Current Baseline:** cold `import forge` median **574 ms** (fresh interpreter).
- **Hypothesis:** deferring the `sqlalchemy`/`parts.db` import until persistence is first touched cuts cold start for the common DB-free path, without changing behavior.
- **Proposed Change:** move the `sqlalchemy` import inside the functions that open a session (lazy import), or defer `parts.db` from the eager `forge` import chain. Preserve `parts/db.py`'s public API.
- **Alternative Options:** measure whether the container/server path always needs the DB (then the win only helps CLI/bench); consider a `--no-db` fast path.
- **Correctness Tests:** full suite green; persistence round-trip tests unchanged; the DB opens correctly on first real use.
- **Benchmark Workload:** cold `import forge`; cold `import forge` + one DB-touching command; startup of the server.
- **Metrics:** cold-start median, first-DB-touch latency (the deferred cost must be measured, not hidden), peak memory.
- **Expected Benefit:** up to ~400 ms off cold start for DB-free paths. **Potential Harm:** the import cost shifts to first DB use (measure it; it must not regress a hot path).
- **Compatibility / Security Risk:** none (same schema/behavior). **Maintenance Cost:** low. **Approval:** touches the persistence import boundary - a change-rule stop-point; confirm before running.
- **Rollback:** restore the eager import.
- **Result / Decision:** **VERIFIED IMPROVEMENT (executed 2026-07-11, approved).** Deferring the
  `parts.db` import (SQLAlchemy's ORM home) out of the three modules on the `import forge` chain
  (`accounts`, `characters`, `session -> job_progress`) via function-local imports cut cold
  `import forge` **680 ms -> 202 ms (~3.4x)**; `sqlalchemy` is verified absent from `sys.modules`
  after `import forge`. The deferred cost is measured, not hidden: `import forge` + first DB import
  = 680 ms (unchanged total), so a DB-touching path (e.g. first login) pays the ~478 ms once, while
  DB-free paths (play/command, benchmarks, most of the tick) never do. `db.py` (the ORM classes)
  is untouched; only WHEN it loads changed. No behavior change: full suite 700 passed, all auth and
  persistence-roundtrip regressions green, mypy clean (135 files). Regression guard: the import-graph
  is implicitly pinned by the suite importing `forge` DB-free. Workload class: **startup-bound**. Level 1.

---

## EXP-004 - Parse seeds with libyaml's CSafeLoader

- **Repository Area:** B (world/seed). `parts/seed.py:_UniqueKeyLoader`, used by `load_rooms`/`load_items`/`load_npcs`/`load_jobs`.
- **Observed Problem:** the seed parser subclassed the pure-Python `yaml.SafeLoader`; the full seed pack parsed at ~51 ms, 100% pure-Python YAML scanner, on the cold-start path (world + npcs load at import).
- **Evidence of Problem / Profiling:** A/B on rooms.yaml - pure-Python SafeLoader 6521 us vs `yaml.CSafeLoader` 486 us = 13.4x on the raw parse; libyaml is available in the venv (`yaml.__with_libyaml__`).
- **Current Baseline:** `load_rooms(first-forge)` end-to-end ~6500 us (parse + validation + room build).
- **Hypothesis:** basing `_UniqueKeyLoader` on `CSafeLoader` moves scanning/composing into C; the parse drops toward the libyaml cost, cutting cold start.
- **Correctness risk + Tests:** `CSafeLoader` composes mappings in C, so the unique-key duplicate gate had to be re-proven. Verified empirically that the C composer **preserves duplicate key pairs** in the node, so `_construct_unique_mapping` still fires. Pinned by `test_duplicate_label_is_rejected` (runs through the active loader) and `test_seed_loader_prefers_libyaml` (asserts the C loader is used when libyaml is present).
- **Compatibility:** falls back to `SafeLoader` where libyaml is absent (`try/except ImportError`), so a host without libyaml still loads seeds (just slower).
- **Result / Decision:** **VERIFIED IMPROVEMENT (executed 2026-07-11).** `load_rooms(first-forge)` end-to-end **~6500 us -> 748 us (~8.7x)** (raw parse 13.4x; the remainder is validation/room-build, unchanged). Duplicate-key gate confirmed still firing under the C loader. Full suite 701 passed (+1 test), mypy clean. No behavior change, no new dependency (PyYAML already vendored libyaml). Workload class: **serialization/startup**. Level 6 (specialized tool, adopted only after profiling proved the win and a correctness re-proof).

---

## EXP-005 - Lazy command seams: defer command-only modules off the import chain

- **Repository Area:** A (server/runtime). `forge.py`'s eager import hub: 20 modules imported at
  the top were used ONLY inside command handlers or the tick fall-through (evolution lab, frameup,
  console, foundry, qualitygate, pm, career, pioneer, law, library, regulations, veritas, workshop,
  terminal, functions, blueprint, architect, loop, generate).
- **Observed Problem:** every engine start paid the import cost of verbs that may never run in
  that process (a benchmark, a CLI invocation, a short session).
- **Evidence / Profiling:** `python -X importtime -c "import forge"` (Windows PC, warm cache):
  our chain 72.5 ms of a 100.5 ms cold start; heaviest command-only subtrees
  `parts.evolution.command` 9.0 ms, `parts.frameup` 6.4 ms, `parts.console` 4.3 ms, plus a long
  tail of ~1-2 ms modules.
- **Hypothesis:** command lambdas resolve module globals at CALL time, so replacing each eager
  import with a module-level wrapper that imports inside its body removes the modules from the
  start chain with zero behavior change; each verb pays its module cost once, on first use.
- **Correctness Tests:** tests import only `COMMANDS`/`handle_command`/`render_scene` from forge
  (verified); full suite green through the wrappers (the engine-tick tests exercise every wired verb).
- **Result / Decision:** **VERIFIED IMPROVEMENT (executed 2026-07-12, Windows PC).** Our import
  chain **72.5 ms -> 41.2 ms (-43%)**; official five-journey startup **95.8 ms -> 68.4 ms (-29%)**.
  Hot paths unchanged (command 3.5 us, combat 4.5 us - the tick's eager imports were not touched).
  The deferred cost is honest: the FIRST use of a lazy verb pays its module import once
  (worst observed subtree ~9 ms on PC); every later use is a dict hit. mypy clean, ruff clean,
  826 passed. Workload class: **startup-bound**. Level 4 (remove duplicate work).
  *(Pi verification pending: expect ~202 ms -> ~140 ms; re-run `python -m benchmarks.perf_journeys`.)*

---

## EXP-006 - Parallelize the `make check` gates (REJECTED)

- **Repository Area:** Makefile. `check: lint typecheck coverage` runs serially.
- **Hypothesis:** running the three gates under `make -j3` cuts wall time to max() instead of sum().
- **Evidence / Measurement (Windows PC, warm caches):** lint 0.1 s, typecheck 0.3 s (mypy
  incremental cache), coverage 9.9 s (pytest -n auto already saturates cores). Serial sum 10.2 s
  vs parallel floor 9.9 s: **a 0.3 s gain, inside run-to-run noise.**
- **Result / Decision:** **REJECTED.** The gates are already ordered cheapest-first, the expensive
  gate already parallelizes internally (xdist), and ruff/mypy incremental caches make the serial
  prefix nearly free. Parallel make would add output interleaving (harder verdict reading) for a
  gain inside noise. Re-open only if a cold-cache CI measurement shows a real win.
