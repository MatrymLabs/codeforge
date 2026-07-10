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
