# PerformanceGate (draft schema)

*Measurement, not mythology.* A draft gate that will eventually compose with the Ritual,
QualityGate, SafetyReview, EvidenceLedger, and VeritasGate. This document is the **schema**;
wiring it into a `parts/` module (with a test twin) is a later, approval-gated step.

## Doctrine

A performance change is a **hypothesis measured against CodeForge's actual workload**, never
adopted because it improved a research benchmark. Sequence: correctness -> baseline ->
profile -> hypothesis -> controlled experiment -> comparison -> decision -> evidence ->
regression protection.

## Statuses

| Status | Meaning |
|---|---|
| `baseline_missing` | no recorded baseline for this journey; cannot compare |
| `measurement_invalid` | benchmark not reproducible, or ran under uncontrolled conditions |
| `correctness_failed` | the correctness suite is red; any timing is meaningless |
| `passed` | within budget and no regression beyond noise |
| `warning` | drifted toward a budget or a small regression within review tolerance |
| `regression_detected` | median regressed beyond the journey's threshold |
| `improvement_detected` | median improved beyond noise, correctness intact |
| `memory_regression` | peak/retained memory regressed beyond threshold |
| `startup_regression` | cold-start regressed beyond threshold |
| `platform_variance` | result inconsistent across platforms without approval |
| `human_review_required` | maintenance cost / security / behavior change needs a decision |
| `optimization_rejected` | gain within measurement noise, or not worth the maintenance cost |
| `experimental_only` | a research track (Rust/Mojo/GPU/compiler) kept as a prototype, not production |

## A change cannot `pass` when

- correctness tests fail;
- the benchmark is not reproducible;
- observable behavior is no longer equivalent;
- maintenance cost is disproportionate to the measured gain;
- security is weakened;
- documentation or evidence is missing;
- platform support breaks without approval;
- **or the apparent gain falls within measurement noise** (median delta < the journey's noise band).

## Record fields (per measured journey)

`journey · commit · branch · python_version · os · processor · cores · memory · workload ·
input · reps · warmup · median_us · min_us · max_us · stdev_us · p95_us · peak_memory_mb ·
io_or_query_counts · timestamp · profiler · status · budget · noise_band · evidence_path`

## Journeys and their workload class (baselined 2026-07-11, Raspberry Pi 5, commit de0f8a5)

| Journey | Median | Workload class | Status |
|---|---|---|---|
| command (`handle_command` rotation) | 8.5 us | CPU / dispatch | `passed` (fast; not a hotspot) |
| combat (single strike) | 10.3 us | CPU | `passed` (fast; not a hotspot) |
| qa gate all (`render_gate_all`) | 8.2 ms -> **2.91 ms** | I/O (was: repeated `stat`) | `improvement_detected` - EXP-002 done (~3.2x; 446->139 stats) |
| catalog search (`reuse_search`) | 39 ms -> **91.8 us** | serialization (was: repeated YAML parse) | `improvement_detected` - EXP-001 done (~426x), now well within budget |
| startup (cold `import forge`) | 574 ms | startup (eager SQLAlchemy import) | `human_review_required` (see EXP-003) |

Reproduce: `python -m benchmarks.perf_journeys` (raw output under `reports/performance/`,
git-ignored but reproducible from the recorded commit).

## Proposed budgets (subject to review; not yet enforced)

- Command response: median <= 50 us (baseline 8.5 us) - generous head-room; user-imperceptible.
- Combat tick: median <= 100 us (baseline 10.3 us).
- Catalog/registry search: median <= 5 ms - **met** (EXP-001: 39 ms -> 0.09 ms; ~426x).
- QA gate all: median <= 5 ms - **met** (EXP-002: 8.2 ms -> 2.91 ms; ~3.2x, shared stat memo + loader cache).
- Cold startup: <= 300 ms (baseline 574 ms) - EXP-003.
- Max permitted regression: median +15% over baseline (else `regression_detected`).

Each budget must eventually carry: user impact, current baseline, target, acceptable
variance, test method, and regression threshold.
