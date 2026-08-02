# SLO: Engine Tick Latency

*A reimplementation of Google's publicly documented SRE error-budget discipline (SRE Book,
ch. 3 "Embracing Risk" and ch. 4 "Service Level Objectives"), built to study service-level
objectives on CodeForge's own engine. It is not affiliated with or endorsed by Google.*

Status: **active** (implemented + tested; evaluated by `make slo`)
Owner: engine
Last reviewed: 2026-07-31

## Why this exists

CodeForge already **measured** its engine tick: `parts/bench.py` drives `handle_command` over a
read-only command rotation and reports a latency distribution, and `make trend` files the median
of each run into the retained Chronicle as the SLI `engine_tick.median_us`. A measurement is not
an objective. This document states the objective, the error budget, and the policy when the budget
is exhausted, so "the engine is fast" becomes a claim with a target and a consequence, not an
adjective.

## SLI (what we measure)

- **Indicator:** `engine_tick.median_us` - the median wall-clock latency, in microseconds, of one
  `handle_command` call over the benchmark rotation (`look`, `help`, `score`, `inventory`).
- **Source of truth:** the Chronicle metric series (`chronicle/ledger.jsonl`, git-tracked,
  hash-chained). One point per recorded run, tagged with the commit it was measured at.
- **How to add a point:** `make trend` (runs the benchmark and appends the median).

The tick is the one door to the world (architecture law 4), and renders never mutate state
(law 1), so the rotation is stable and repeatable: the SLI measures the same thing every run.

## SLO (the objective)

> **>= 99% of recorded runs keep `engine_tick.median_us` at or below 150 microseconds.**

Grounding (honest, host-relative): on the reference host (Raspberry Pi 5, aarch64, Python 3.13)
the measured baseline is:

| Statistic | Value |
|-----------|-------|
| median (the SLI) | ~58 us |
| p95 (per call) | ~123 us |
| p99 (per call) | ~849 us |
| throughput | ~12,300 commands/sec |

The 150 us threshold is ~2.6x headroom over the measured median: loose enough to absorb host
jitter and a shared CPU, tight enough that a recorded median above it signals a **real**
regression (the optimization campaign drove the dominant `look` path from ~42 ms to ~150 us; a
median tick north of 150 us would mean something regressed hard). The threshold and the objective
are host-relative and are inputs to `make slo` (`make slo <threshold_us> <objective_pct>`), not
constants baked into the meaning of "fast."

## Error budget

The error budget is the complement of the objective:

```
error budget = 1 - SLO = 1 - 0.99 = 0.01  (1% of recorded runs may breach the threshold)
```

Over `N` recorded runs, the budget permits `N x 0.01` breaches. `kernel/slo.py` computes how much
of that budget has been burned:

```
allowed_bad          = samples x (1 - SLO)
budget_consumed_pct  = breaches / allowed_bad x 100
```

- **pass** - budget burn below 75%.
- **watchlist** - budget burn at or above 75% but not yet overspent.
- **breach** - breaches exceed `allowed_bad`: the budget is exhausted.
- **no-data** - no SLI points recorded yet (reported honestly; absence is never a false pass).

**Honest limitation (sample count):** a 99% objective needs at least 100 recorded runs before the
budget even allows a single breach. Below that, one breach trips the whole budget, so `make slo`
flags the verdict as not-yet-meaningful and names how many runs are needed. The budget is a
discipline for a growing series, not a verdict on one measurement.

## Policy when the budget is exhausted (breach)

Mirroring the SRE error-budget policy, adapted to this repo:

1. **Freeze latency-risking changes** to the tick and its hot path until the median is back under
   threshold. Correctness/security fixes are always allowed; new features on the hot path wait.
2. **Open a Chronicle incident** (`chronicle record-incident`) and, if a specific change caused it,
   file a **counterexample** so the regression is durable memory, not a repeat.
3. **Diagnose with evidence, not intuition** (`make bench`, the benchmarks in `benchmarks/`,
   `cProfile`) - find the actual bottleneck before optimizing (the optimization ladder).
4. **Write a postmortem** (`docs/postmortem_template.md`) if the breach reached a running server.

`make slo` returns exit code 1 on a breach so a pipeline can act on it. It is deliberately **not**
wired into `make check`: the SLI is host-relative and sparse, so gating every merge on one host's
latest measurement would be dishonest. The SLO is evidence and a policy, not a merge gate.

## What I would do differently at 100x scale

At a single-process, single-host engine the SLI is a median-of-run and the budget is a weekly-ish
series. At 100x (many shards, many hosts, real players):

- **Per-shard, per-host budgets.** Latency is host-relative; one global number would hide a slow
  shard. Each shard carries its own budget; the fleet SLO is the aggregate.
- **Live SLIs, not benchmark runs.** Measure real player commands (tagged by verb) with a latency
  histogram, and compute the SLO as "% of real commands under threshold," not "% of bench runs" -
  the SRE definition. The benchmark becomes the pre-merge canary; production traffic becomes the SLO.
- **Burn-rate alerting.** Alert on the *rate* the budget is consumed (fast-burn vs slow-burn
  windows), not just end-of-window exhaustion, so a sudden regression pages before the budget is gone.
- **Multi-window multi-burn-rate** thresholds per the SRE Workbook, to trade alert precision against
  recall.

These are noted, not built: claiming them without the load and traffic to measure would be theater.
Batch 3 of this campaign adds a load test that captures a real latency histogram feeding this budget.

## How to evaluate

```
make slo                 # evaluate the default objective (>=99% under 150us)
make slo 200 99.9        # a different threshold / objective, ad hoc
make trend               # record one more SLI point, then show the series
```

## Provenance

Original implementation (`kernel/slo.py`, `catalog/parts.yaml` id `slo-error-budget`). The
error-budget formula and the SLI/SLO/error-budget vocabulary are the public Google SRE pattern;
no code was copied. The Chronicle SLI series and the benchmark it reads are pre-existing CodeForge
parts. Honest labels throughout: the baseline numbers are measured on one host and compare only
within that host.
