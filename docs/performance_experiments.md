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
  bad edit fails loud and is never cached. Full suite 673 passed (+4 cache tests), 93.30%
  coverage. No behavior change, no new dependency. Regression guard: the parse-once and
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
