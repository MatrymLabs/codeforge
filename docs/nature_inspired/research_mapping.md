# Research mapping: Nature-Inspired Design -> CodeForge

*How the report "Nature-Inspired Design for an AI Coding Assistant" translates into CodeForge
engineering. The rule: nature inspires, engineering translates, tests verify, metrics compare,
Josh decides. This document carries the report's own evidence labels honestly - a metaphor is
never presented as proof, and no mechanism is claimed to improve CodeForge until it is measured
inside CodeForge.*

## Evidence labels (used in every row)

- **Evidence-backed** - a peer-reviewed / venue-verified result transfers with a clear mechanism.
- **Extrapolation** - a reasonable engineering translation from adjacent (often preprint) work.
- **Experimental** - worth a careful pilot; weak direct evidence for this use case.
- **Future** - deferred by design.
- **Not recommended** - the report rates it low/very-low feasibility for a software product.

## The mapping

| Nature-inspired mechanism | CodeForge translation | Label | Feasibility / Evidence (report) | Existing system it composes with | Source |
|---|---|---|---|---|---|
| Candidate populations (keep 3-5 variants alive, archive elites) | A small `Candidate` population per genome; elite baseline preserved; never auto-promote | **Evidence-backed** | High / High - Build now | Blueprint, Registry, reports/ | Romera-Paredes et al. (2024, *Nature*) |
| Genotype -> phenotype separation | `BlueprintGenome` (typed genotype) expresses into code/tests/config/docs (phenotype) | **Evidence-backed** | High / High - Build now | `parts/blueprint.py` (the seed) | Pantridge & Helmuth (2023, GECCO) |
| Type-safe mutation operators | A registry of explicit, auditable operators; **v1 applies none autonomously** | **Evidence-backed** | High / High - Build now (design only in v1) | (new) | Pantridge & Helmuth (2023, GECCO) |
| Multi-objective fitness | Hard gates first (correctness/security/tests/policy), then weighted objectives, every metric visible | **Evidence-backed** | High / High - Build now | VeritasGate, QualityGate, SafetyReview | Solovyeva et al. (2025) |
| Counterexample bank | Every failure -> normalized signature -> regression test -> permanent fitness knowledge | **Evidence-backed** | High / Medium-high - Build now | reports/, Classroom (lessons) | Helmuth et al. (2024) |
| Sparse event-driven control plane | Wake only the subsystems an event touches; bounded queues; interrupt lane for security/policy | **Extrapolation** | High / Medium - Build now | `parts/events.py` | Srivatsav et al. (2023); Su et al. (2024); Frank et al. (2025) |
| Context region-of-interest selection | Select the smallest relevant files/symbols before expensive AI/analysis | **Extrapolation** | High / Medium - Build now | import graph, Registry | Arjmand et al. (2024) |
| Bounded evaluator swarm | Specialized read-only evaluators that score + explain; **no merge authority, no self-approval** | **Extrapolation** | Medium-high / Medium - Build soon | QualityGate, VeritasGate, AI seam | SOEN-101 (2024) |
| Hierarchical multicast encoding | Efficient evaluator/subscriber fan-out at scale | **Future** | Medium / Medium - when scale demands | event bus | Su et al. (2024) |
| DNA-like constraint codes | Make illegal combinations (bad deps, unmigrated persistence, illegal API rewrites) inexpressible | **Experimental** | Medium / Medium - pilot carefully | constraint pre-check | Nguyen et al. (2023); Milenkovic & Pan (2023) |
| Self-healing / quarantine controller | Detect, quarantine a bad candidate, roll back to elite; **never touch production/auth/branches** | **Experimental** | Medium / Medium-low - pilot carefully | RepoIntegrityRitual | (biomimetic heuristic) |
| Compiled hotspot kernels (Rust/MLIR) | Surgical, only where profiling proves a hotspot | **Not recommended (here)** | Medium / High - use surgically | perf gate | Harding & Dunlavy (2025); Godoy et al. (2025) |
| Neuromorphic hardware | Run the assistant on a neuromorphic chip | **Not recommended** | Low - do not pursue | - | Srivatsav et al. (2023) |
| Molecular / DNA execution | Literal biochemical computation | **Not recommended** | Very low - novelty only | - | Milenkovic & Pan (2023) |

## The synthesized pattern (the report's "Blueprint Evolution Lab")

```
Human intent -> Requirements -> Typed Blueprint Genome -> Candidate population
  -> Controlled expression -> Tests + evaluations -> Fitness (hard gates, then weighted)
  -> Counterexample capture -> Human review -> Approved implementation -> Evidence + archive
```

Keep 3-5 candidates alive; score with hard gates first; preserve at least one elite baseline;
mutate only through typed, auditable operators; archive every failure as a counterexample. This
is closer to the literature than "let the model keep rewriting until it looks good."

## Governance (Human Keel Doctrine)

AI may create candidates, propose mutations, generate drafts + tests, run approved evaluations,
and recommend promotion. AI may **not** promote candidates, replace the elite baseline, weaken
safety, change protected interfaces, or bypass human approval. Josh is the final authority.
Policy modes: `learning_mode`, `prototype_mode`, `review_mode`, `optimization_mode`,
`release_mode`. High-agency human review stays **outside** any autonomous search loop -
especially for security-sensitive edits, public APIs, persistence, and destructive actions.

## Cost discipline (measurement-first, per the optimization ethos)

Do not assume the architecture improves anything. Every run ships explicit compute/token budgets
and a stopping policy; v1 limits: <= 3 candidates, 1 generation, <= 2 operators/candidate,
<= 1 evaluator retry, a configurable duration/token cap, and a kill switch. Measure: time to
approved implementation, candidate success rate, regressions escaped, counterexamples reused,
tokens consumed, runtime/memory, accepted diff size, rollback frequency. Preserve raw data.

## References (APA 7)

Arjmand, C., Xu, Y., Shidqi, K., Dobrita, A. F., Vadivel, K., Detterer, P., Sifalakis, M.,
Yousefzadeh, A., & Tang, G. (2024). *TRIP: Trainable region-of-interest prediction for
hardware-efficient neuromorphic processing on event-based vision* [Preprint]. arXiv.

Frank, G., Hota, G., Wang, K., Uppal, A., Olajide, O., Yoshimoto, K., Gibb, L., Wang, Q.,
Leugering, J., Deiss, S., & Cauwenberghs, G. (2025). *HiAER-Spike: Hardware-software co-design
for large-scale reconfigurable event-driven neuromorphic computing* [Preprint]. arXiv.

Godoy, W. F., Melnichenko, T., Valero-Lara, P., Elwasif, W., Fackler, P., Ferreira Da Silva, R.,
Teranishi, K., & Vetter, J. S. (2025). *Mojo: MLIR-based performance-portable HPC science kernels
on GPUs for the Python ecosystem*. In Workshops of the International Conference for High
Performance Computing, Networking, Storage and Analysis. ACM.

Harding, K., & Dunlavy, D. M. (2025). *Improving runtime performance of tensor computations using
Rust from Python* [Preprint]. arXiv.

Helmuth, T., Pantridge, E., Frazier, J. G., & Spector, L. (2024). *Generational computation
reduction in informal counterexample-driven genetic programming* [Preprint]. arXiv.

Keuning, H., Alpizar-Chacon, I., Lykourentzou, I., Beehler, L., Koppe, C., de Jong, I., &
Sosnovsky, S. (2024). *Students' perceptions and use of generative AI tools for programming across
different computing courses* [Preprint]. arXiv.

Milenkovic, O., & Pan, C. (2023). *DNA-based data storage systems: A review of implementations and
code constructions* [Preprint]. arXiv.

Nguyen, T. T., Cai, K., Kiah, H. M., Dao, D. T., & Schouhamer Immink, K. A. (2023). *On the design
of codes for DNA computing: Secondary structure avoidance codes* [Preprint]. arXiv.

Pantridge, E., & Helmuth, T. (2023). *Solving novel program synthesis problems with genetic
programming using parametric polymorphism* [Peer-reviewed conference paper]. GECCO 2023.

Romera-Paredes, B., Barekatain, M., Novikov, A., Balog, M., & Kumar, M. P. (2024). *Mathematical
discoveries from program search with large language models*. Nature.

Solovyeva, L., Weidmann, S., & Castor, F. (2025). *AI-powered, but power-hungry? Energy efficiency
of LLM-generated code* [Preprint]. arXiv.

Srivatsav R, M., Chakrabartty, S., & Thakur, C. S. (2023). *Neuromorphic computing with AER using
time-to-event-margin propagation* [Preprint]. arXiv.

Stoico, V., Dragomir, A. C., & Lago, P. (2025). *An empirical study on the performance and energy
usage of compiled Python code* [Preprint]. EASE 2025.

Su, Z., Bencsik, A., Indiveri, G., & Bertozzi, D. (2024). *An efficient multicast addressing
encoding scheme for multi-core neuromorphic processors* [Preprint]. arXiv.

*SOEN-101: Code generation by emulating software process models using large language model agents*
(2024) [Preprint]. arXiv:2403.15852.
