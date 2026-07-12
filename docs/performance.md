# Performance evidence (`make bench`)

*The engine tick (`handle_command`) is the one door to the world (architecture law 4). Its
speed is a measured number with a distribution, not a claim.*

## Run it

```
make bench          # full run (20k samples), prints the report and files dated evidence
terminal bench      # a quick in-game run (5k samples), framed like the other programs
```

`make bench` files a dated report under `reports/performance/` (git-ignored; reproducible
from the recorded commit, per the evidence-discipline rule).

## What it measures

A read-only command rotation (`look`, `help`, `score`, `inventory`) driven through the real
tick. The rotation never mutates world state (renders are projections, law 1), so successive
samples are comparable and the run repeats. It reports throughput (commands/sec) and the
latency distribution (median, p95, p99, max).

## Method notes (honest)

- **Frameless.** stdlib `time.perf_counter` + `statistics`; no benchmark framework
  (`parts/bench.py`). The `bench` in the tooling matrix stays `stdlib_first`.
- **Warmup.** The first calls resolve imports and build the command table; a warmup pass
  runs before the timed loop so those one-time costs are not counted.
- **Host-relative.** Numbers scale with CPU (measured on a Raspberry Pi 5). The report says
  so; the value is the *shape* (sub-10us median, tight p95) and the reproducible method, not
  a headline number to quote out of context.
- **Read-only rotation** is a floor, not a worst case: mutating commands (combat, movement,
  crafting) do more work. This measures dispatch + render, the hot path every command pays.

## Why it is here

Performance evidence is a scored portfolio dimension. This gives codeforge its own tick
benchmark (the deep GPU/CPU performance study lives in the sibling `pyg-perf-lab`), proving
the engine's hot path with a reproducible artifact rather than an assertion.

## The five critical journeys (measurement foundation)

Beyond the tick, a measurement harness baselines the five journeys an audit cares about:

```
python -m benchmarks.perf_journeys   # startup · command · combat · qa gate · catalog search
```

It reuses the same frameless method (stdlib `perf_counter` + `statistics`, warmup, median +
distribution); startup is measured cold (a fresh interpreter), the rest warm. Raw output lands
under `reports/performance/` (git-ignored, reproducible). Baselines on a Raspberry Pi 5
(commit de0f8a5): command 8.5us and combat 10.3us are fast (not hotspots); the measured
hotspots are I/O/serialization/startup-bound, not CPU kernels -

- catalog search **39 ms** (99% is re-parsing the YAML catalog every call),
- qa gate all **8.2 ms** (~446 `stat` calls per run),
- cold startup **574 ms** (SQLAlchemy imported eagerly ~412 ms).

See [performance_gate.md](performance_gate.md) (the PerformanceGate draft + budgets),
[performance_research_map.md](performance_research_map.md) (the research-to-CodeForge evidence
map, APA-cited), and [performance_experiments.md](performance_experiments.md) (one experiment
card per hotspot - proposals, not yet run). Doctrine: **AI proposes, the profiler observes,
the benchmark compares, the tests verify, the engineer decides.**

## Cross-platform comparison (Pi 5 vs Windows PC)

| Journey | Pi 5 median (de0f8a5) | PC median (Win11, same commit) | Speedup |
|---------|----------------------|-------------------------------|---------|
| Startup (cold) | 202 ms | 95.3 ms | ~2.1x |
| Command | 8.5 μs | 3.4 μs | ~2.5x |
| Combat | 10.3 μs | 4.4 μs | ~2.3x |
| QA Gate All | 2.91 ms | 2.69 ms | ~1.1x |
| Catalog Search | 91.8 μs | 242.7 μs | 0.4x (Pi faster) |

> PC run: 2026-07-12, Windows 11, Python 3.13.12. The catalog search regression on PC
> likely reflects filesystem/YAML-parse differences on Windows vs Linux aarch64 — worth
> investigating if it becomes a bottleneck. The hot-path commands (command, combat) are
> CPU-bound and scale with clock speed as expected.
