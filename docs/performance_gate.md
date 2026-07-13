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
| qa gate all (`render_gate_all`) | 8.2 ms baseline (current: see raw) | I/O (was: repeated `stat`) | EXP-002 shipped the shared stat-memo + loader cache; current median is high-variance on this host - read the raw artifact, not a figure typed here |
| catalog search (`reuse_search`) | 39 ms baseline (current: see raw) | serialization (was: repeated YAML parse) | EXP-001 shipped (parse-once loader cache; ~426x); current median well within budget - see raw |
| startup (cold `import forge`) | 680 ms baseline (current: see raw) | startup (was: eager SQLAlchemy import) | EXP-003 shipped (SQLAlchemy import deferred to first DB touch); cold-start median is host/load-sensitive - see raw |

Note: the before ("baseline") figures record the dated optimization experiments; the CURRENT
median for each journey lives in the raw artifact (below), never a hand-transcribed number here.
An earlier revision of this table hard-coded post-optimization figures (2.91 ms, 202 us, 202 ms)
that drifted from the committed raw run; those are removed in favor of the reproducible source,
the same discipline the README uses for the test count (the badge is the live source, not prose).

Reproduce: `python -m benchmarks.perf_journeys` (raw output under `reports/performance/`,
git-ignored but reproducible from the recorded commit).

## Proposed budgets (subject to review; not yet enforced)

- Command response: median <= 50 us (baseline 8.5 us) - generous head-room; user-imperceptible.
- Combat tick: median <= 100 us (baseline 10.3 us).
- Catalog/registry search: target median <= 5 ms. EXP-001 shipped the parse-once loader cache
  (~426x off a 39 ms baseline); the committed raw median is well within the target - see the artifact.
- QA gate all: target median <= 5 ms. EXP-002 shipped the shared stat-memo + loader cache off an
  8.2 ms baseline; the committed raw median on this host is higher and high-variance, so this line
  does NOT assert "met" - the raw artifact is the source of the current number.
- Cold startup: target <= 300 ms. EXP-003 shipped the deferred SQLAlchemy import off a 680 ms
  baseline; the committed cold-subprocess median on this host is higher (host/load-sensitive), so
  read the raw artifact rather than a claim typed here.
- Max permitted regression: median +15% over baseline (else `regression_detected`).

Each budget must eventually carry: user impact, current baseline, target, acceptable
variance, test method, and regression threshold.
