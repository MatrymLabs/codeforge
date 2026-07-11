# Research-to-CodeForge evidence map

Five research papers, mapped to CodeForge with an explicit *do-not-overgeneralize* warning per
row. The recurring lesson: the exotic optimization tracks (Rust, Mojo/GPU, the big compiler
wins) demonstrate their gains on loop-heavy numeric kernels, data-parallel GPU science, or
compute microbenchmarks with no third-party libraries - workloads CodeForge does not have.
CodeForge's measured hotspots are I/O-, serialization-, and startup-bound, fixable in pure
Python. The research is, in effect, evidence *against* premature exotic optimization here.

APA in-text citations map to the reference list at the bottom.

| Research finding | CodeForge implication | Repo area | Experiment required | Do-not-overgeneralize | Citation |
|---|---|---|---|---|---|
| Rust-from-Python: >2 orders vs pure-Python loop tensor kernels, only comparable to Numba/NumPy once vectorized; FFI first-call ~1e-4 s | No loop-heavy numeric kernel exists; FFI overhead would dominate tiny inputs | combat, world, registry | Only if a measured CPU kernel with large repeated input appears | Result is over naive loops on 10^3-10^8 arrays; our inputs are <= hundreds | (Harding & Dunlavy, 2025) |
| Mojo: 87-96% of CUDA/HIP on memory-bandwidth-bound GPU kernels; gaps on compute/atomics; steep, immature, closed until 2026 | No massively data-parallel numeric workload; GPU launch/transfer would exceed benefit | (none) | None until a real parallel numerical workload is measured | Stencil/BabelStream/BUDE on H100/MI300A; irrelevant to text commands | (Godoy et al., 2025) |
| Codon/PyPy/Numba >90% speed+energy on compute-heavy, single-threaded, no-third-party-lib microbenchmarks; AOT C-transpilers small/negligible, sometimes worse (n_body -55%..-69%) | Codon likely incompatible (lib support); PyPy risky (C-ext deps); Numba n/a; mypyc the only plausible candidate for a hot well-typed pure module | compiler track; pure modules (stats, derived, progression, statemachine) | Measure mypyc on one profiled-hot, dependency-free module | Wins are on numeric CLBG code without libraries; we are I/O- and library-bound | (Stoico, Dragomir, & Lago, 2025) |
| LLM Python code often as-efficient-or-better than human, machine-agnostic; weaker on Sorting/Graph/Greedy/Math/Recursion | Do not assume AI-written code here is broadly slow; scrutinize those algorithm classes | search/sort/registry/recursion | Targeted review of sort/search/recursive routines, then measure | Tasks are LeetCode "hard"; correlation != our code | (Solovyeva, Weidmann, & Castor, 2025) |
| Students who "drift" accept AI output without understanding; value is critical use + understanding | Our tests + VeritasGate + evidence + "what did Josh learn" is the governance counter; Professor Codex teaching profiling fits "learning uniqueness" | QA/Veritas, Classroom | Require purpose/tests/evidence/learned per AI-assisted change | Perceptions survey (one university, self-report); justifies process, not a code metric | (Keuning et al., 2024) |

## Exotic-track verdicts (research-determined)

- **Rust (PyO3/Maturin): not justified** - no measured loop-heavy CPU kernel (Harding & Dunlavy, 2025).
- **Mojo / GPU: inappropriate** - no data-parallel numerical workload (Godoy et al., 2025). Future research only.
- **Compilers: measure-first, single candidate (mypyc)** on a profiled-hot, well-typed, dependency-free module; expectations tempered by the AOT-transpiler results (Stoico et al., 2025).

## References

Godoy, W. F., Melnichenko, T., Valero-Lara, P., Elwasif, W., Fackler, P., Ferreira Da Silva, R., Teranishi, K., & Vetter, J. S. (2025). *Mojo: MLIR-based performance-portable HPC science kernels on GPUs for the Python ecosystem*. arXiv. https://arxiv.org/abs/2509.21039

Harding, K., & Dunlavy, D. M. (2025). *Improving runtime performance of tensor computations using Rust from Python*. arXiv. https://arxiv.org/abs/2510.01495

Keuning, H., Alpizar-Chacon, I., Lykourentzou, I., Beehler, L., Köppe, C., de Jong, I., & Sosnovsky, S. (2024). *Students' perceptions and use of generative AI tools for programming across different computing courses* (Version 2). arXiv. https://arxiv.org/abs/2410.06865

Solovyeva, L., Weidmann, S., & Castor, F. (2025). *AI-powered, but power-hungry? Energy efficiency of LLM-generated code*. arXiv. https://arxiv.org/abs/2502.02412

Stoico, V., Dragomir, A. C., & Lago, P. (2025). *An empirical study on the performance and energy usage of compiled Python code*. arXiv. https://arxiv.org/abs/2505.02346
