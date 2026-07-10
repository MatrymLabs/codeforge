# Pioneer Experiment: build a GPU performance package on a GPU-less host

**Date:** 2026-07-10 · **Risk level:** 2 (controlled prototype) → new repo, pushed (L4, approved)

**Mission:** deliver a runnable PyCharm + PyTorch Geometric (GNN) performance package —
profilers, benchmarks, CI, docs — that proves ML-infra / performance-engineering skill.

**Hypothesis:** a GPU-less host (this Raspberry Pi, aarch64, no CUDA) does *not* block the
project. The "must have a GPU" assumption is a **habit**, not a hard constraint — the CPU
path is real and verifiable, and the GPU path can be *authored honestly* and verified later
on a real CUDA box.

**Constraint challenged (habit, not limit):** "you can't build/verify GPU tooling without a
GPU." Reframed: split the work by what each host can *honestly* prove. Verify what runs;
mark what doesn't. The real constraint is **truth**, not hardware.

**Safety gates kept:** VeritasGate honesty (nothing claimed as measured that wasn't run);
`make check` green; framework-free codeforge untouched (the package is its **own** repo,
per ADR-0003); a documented, disabled self-hosted GPU CI lane (no unverifiable green).

**Prototype:** `pyg-perf-lab` — `torch.profiler`, `NeighborLoader`/`PrefetchLoader`, AMP,
`torch.compile(dynamic=True)`, a CUDA-sync timing harness, device resolution that reports a
`cuda→cpu` fallback *loudly*. Torch is an optional extra so lint/type/tests run with no 2 GB
install.

**Test result:** on this Pi — `make check` green (ruff + mypy + 9 tests, no torch); with
torch installed, the CPU benchmark + `torch.profiler` ran for real. The profiler measured
**`aten::scatter_add_` at ~32% self-CPU** — the textbook GNN gather-scatter hotspot. PyG's
neighbor sampler (needs `pyg-lib`/`torch-sparse`, no aarch64 wheel) was **gracefully
skipped with a note**, not crashed.

**Evidence:** `pyg-perf-lab/docs/sample_cpu_run.md` (dated CPU snapshot); CI green on the
CPU matrix (3.10/3.11/3.12) at github.com/MatrymLabs/pyg-perf-lab; GPU paths marked
*"verify on a CUDA host"* throughout.

**Decision:** shipped. The honest split is *stronger* than a faked "GPU-verified" dump —
the verification status itself reads as engineering maturity.

**Rollback:** the package is a standalone repo; it changes nothing in codeforge. Revert =
archive/delete the repo. No fleet coupling.

**Next move:** run the GPU scripts on the CUDA box (`--device cuda --amp --compile`), drop
the output into `sample_cpu_run.md`'s GPU section, and enable the self-hosted GPU CI lane —
flipping the GPU rows from *authored* to *verified*.
