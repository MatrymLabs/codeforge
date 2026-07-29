# Knowledge Convergence Audit (2026-07-28)

*One final synthesis pass over the project's external research corpus (~26 documents, ~400 pages:
portfolio/hiring, engineering patterns, secure coding, fraud/waste/abuse, clinical high-reliability,
1990s MUD codebases, a MUD i18n design, performance engineering, nature-inspired AI, and five arXiv
papers) read against the repo's own canon (14 codeforge ADRs, 3 fleet ADRs, and the doctrine docs).*

**Purpose.** Determine whether one comprehensive review reveals insights previously missed, and
report only genuinely new findings. It does not restate documented canon except where load-bearing.

**Honest bound up front.** Roughly three quarters of the corpus *confirms* existing canon (the
security gates, the optimization ladder, the human-keel doctrine, the evidence discipline,
readiness-not-compliance, the entry/intermediate/advanced coverage ladder). That confirmation is
valuable but not new. The material delta is about one fifth, recorded below with an explicit
disposition for each item so nothing is silently adopted or silently dropped.

---

## The meta-finding

**Six unrelated professional literatures independently converged on CodeForge's control
architecture.** Secure coding, fraud/waste/abuse and supply-chain, clinical high-reliability,
nature-inspired computing, historical MUD design, and CS education each, in their own vocabulary,
reinvented the same five primitives:

1. canonical state, projected text (renderers never mutate),
2. evidence gates before irreversible action,
3. separation of duties,
4. bounded autonomy,
5. human escalation,

plus an append-only regression memory.

The canon currently *asserts* the cross-domain-composition thesis. This corpus *corroborates* it from
six directions that never cite one another. That converts a claim into evidence, which is the whole
point of "no claim without correspondence." It is the strongest thing this audit found, and it was
not previously written down.

**Disposition:** promote to canon as a short doctrine doc (the evidence for the composition thesis).

---

## Findings by category

Each finding is tagged NEW (genuinely additive) or CONFIRMS (validation only), with a disposition:
BUILD (no keel decision needed), DOC (a dedicated reference gap), CANON (a doctrine to record),
JUNCTION (a keel decision for Josh), or ARCHIVE (retire or decline).

### 1. New engineering insights
- **[NEW / BUILD] Counterexample bank.** The single most convergent unbuilt idea: it surfaced
  independently in three clusters (testing, FWA, nature-inspired). A durable, accumulating store where
  every flaky failure, surviving mutant, blocked hallucinated package, and escaped defect becomes a
  permanent regression input. Canon has the convention ("hostile test cases") and a mutation-testing
  doc, but not the durable artifact. *Impact: high, small slice, composes with the RepoIntegrityRitual.*
- **[NEW / BUILD] The polyglot speedup claims lack an in-repo evidence artifact.** The native-organ
  numbers meet the eye but not the ethos standard (before/after, first-call overhead, parity) in
  writing. The arXiv Rust-from-Python paper is the honesty anchor: its toy kernels reached far higher
  multiples than our real kernel, which makes our measured figure the *more* credible one, when it is
  recorded. *Impact: medium; closes a claim-without-correspondence gap on the flagship's headline.*
- **[CONFIRMS] The optimization ladder** (measure before optimize; escalate only on evidence) is
  restated by three independent performance sources. Validation, not news.

### 2. New architectural insights
- **[NEW / DOC] No documented concurrency or thread-safety model, and the gateway is threaded over
  shared world state.** Neither the repo nor the 400 pages of research addresses it. This is the
  actual hard problem of a live MUD and the one thing both are silent on. *Impact: high; the most
  important undocumented risk surfaced.*
- **[NEW / JUNCTION, defer build] The interlingua canonical-frame schema is the concrete shape the
  typed-events backlog has lacked.** A typed event frame (actor/intent/verb/args/world-refs) is
  Architecture Laws 1 and 4 generalized. Adopting it as the internal representation of the tick is a
  legitimate low-risk refactor; the full multilingual engine (NMT workers, pgvector, orchestration)
  is scope creep against the north star. *Disposition: name the frame as design intent; build only
  the typed-event slice, and only on Josh's go.*
- **[NEW / JUNCTION] Evolve the event bus into a "signal economy":** sparse wake-only-what-cares
  fan-out, a priority lane for security/destructive/public-API events, a region-of-interest selector
  before expensive work.

### 3. Newly discovered patterns
- **[NEW / CANON] The five-primitive control spine** (see meta-finding) is the discovered pattern:
  canon has the pieces, never the unifying invariant.
- **[NEW / CANON] "Evaluators produce evidence, not merge authority."** The crispest one-sentence
  sharpening of the QA spine plus human keel: scoring agents never write to trunk.
- **[NEW / CANON, metaphor] Genotype/phenotype with illegal-states-inexpressible mutation** re-expresses
  the frozen-identifier and architecture-law boundaries in the Forge voice (a candidate can no more
  evolve into an unsafe state than DNA into an inactive fold). A promotable metaphor that fights nothing.

### 4. Hidden dependencies
- **[NEW / CANON] Duplicate-source-of-truth trap.** Counterexample bank, AuditLedger, evidence_store,
  Chronicle, and the ai-log-triage compliance plane are five names for one append-only evidence
  artifact. Building them separately would violate "no duplicate source of truth." *Decide the one
  store before building any.*
- **[NEW / BUILD] forge-audit and every auto-evaluator depend on the frozen `parts/` layout.** The
  keystone portfolio-checklist research and four other docs hardcode `src/`. An evaluator pointed at
  CodeForge scores the flagship wrong unless taught `parts/`. *Make forge-audit layout-aware; note it
  in the layout ADR.*

### 5. Opportunities for simplification
- **[CONFIRMS] Harvest, don't import.** The full-stack-patterns doc recommends roughly fifteen
  libraries for patterns CodeForge already owns as parts. Reaffirms the Hardware Store; supplies a
  concrete decline-list.
- **[NEW / minor] Fold the part/service/classroom "templates" into the existing Seed/Blueprint idea**
  rather than parallel-building them.

### 6. Opportunities for standardization
- **[NEW / CANON] Promote the empirical benchmark statistical toolkit** to the standard shape of the
  performance-evidence gate: non-parametric tests (Mann-Whitney/Kruskal-Wallis), effect sizes (Cliff's
  delta / Hedges' g), core-pinning, warm-up, multi-platform blocking, a replication package. Three
  arXiv labs converged on it independently.
- **[NEW / CANON] Non-overridable escalation classes.** Some failures (security, evidence-absence)
  must never auto-proceed. A small hardening of the critical-junction rule.
- **[NEW / BUILD] `CITATION.cff`** is absent, cheap, and uniquely fitting for a doctoral-student
  portfolio.
- **[NEW / DOC] Numba-vs-Rust decision record for the polyglot ADR.** Rust's FFI first-call overhead
  is far smaller than Numba's JIT warm-up (the honest reason to pick Rust); Numba is the cheaper
  decorator-only fallback worth benchmarking against; ahead-of-time-to-C++ compilers are a trap on
  math-heavy loops.

### 7. Potential risks
- **[NEW / ARCHIVE] Identity drift toward web full-stack.** Four portfolio docs push
  React/Next/FastAPI/Postgres; following them means new repos outside the thesis. The corrective is
  inside the same cluster: the honest market is tooling, platform, SRE, QA-automation, technical
  writing, and game-tooling, which CodeForge already fits. *Decline the web-app identity.*
- **[NEW / JUNCTION] Five scope-creep gravity wells.** Each cluster invited reframing the flagship:
  clinical operating system, AI coding assistant / Blueprint Evolution Lab, multilingual engine,
  OS/K8s patch management, an AURA pedagogy subsystem. Each is a keel junction, not a plank, and each
  competes with the "complete the AAA game" north star. *File all five as Research/Experiment, none as
  Immediate.*
- **[NEW / CANON] Preprint-maturity caveat.** FWA, clinical, and nature-inspired sources lean on
  arXiv preprints self-labeled "design hypotheses, not universal truths." Any canon that cites them
  inherits that label, exactly as the authority-tiers and readiness-not-compliance rules require.
- **[NEW / CANON] Legal.** Do not ingest Merc/ROM/SMAUG/GodWars/LPMud code (study-only,
  non-commercial); one distributed license file was spam-injected, so verify against clean tarballs;
  keep the SPDX/attribution ledger. Reinforces the existing legacy-MUD clean-room discipline.
- **[OPERATIONAL] Credential exposure (not a repo finding).** Recovery-code files are sitting in a
  sync-prone downloads folder; move them to a password manager.

### 8. Missing research areas
- **[NEW] Games / MUD engines / tick-simulation as a portfolio category: zero coverage.** Every hiring
  doc frames web apps, CLIs, data pipelines, or ML. None tells you how to present a game engine to a
  reviewer. CodeForge's largest unaddressed positioning question.
- **[NEW] Frameless / stdlib-first as a defensible choice has no external validation** in the corpus;
  CodeForge's frameless thesis is arguably ahead of its sources and needs its own written defense.
- **[NEW] Honest presentation of AI-assisted authorship** (the Human Keel problem) is assumed away by
  the research; CodeForge's ownership-gate doctrine is ahead of the literature, a differentiator to
  document rather than consume.
- **[NEW / DOC] Dedicated-reference gaps:** telnet wire protocol, threat model for the command
  surface, data-model / schema catalog, engine-side accessibility. The principles exist scattered in
  CLAUDE.md; the discoverable doc does not.

### 9. Ideas worth promoting to canon (ranked by value-to-effort)
1. The five-primitive convergence doctrine (the meta-finding).
2. The counterexample bank.
3. The empirical benchmark statistical toolkit standard.
4. Non-overridable escalation classes.
5. The behavioral dependency-admission screen (hallucinated/malicious-package intake, beyond the
   known-CVE model) folded into the existing Technology Intake gate.
6. The three market-narrative positioning sentences into the README and Career Board.
7. `CITATION.cff`.
8. The interlingua frame as documented design intent (build deferred).

### 10. Ideas to archive or remove
- **The Evennia-port premise.** Stale, and it saturates the MUD-research corpus (it is even in one
  document's title). Formally retire it in the legacy-MUD provenance narrative so future readers do
  not treat those recommendations at face value.
- **The MUD-client POC report** is superseded by the shipped codeforge-client; mark "historical
  input, delivered."
- **The `src/` migration** is already a recorded non-recommendation; close it formally (frozen `parts/`).
- **Decline:** `tox` (duplicates `make check`), the web-app identity (Next/FastAPI/Django as
  CodeForge's shape), AURA pedagogy planning (keep AURA reserved-but-unbuilt), and the do-not-pursue
  set (Mojo watch-only, neuromorphic/DNA execution, OPA/Rego, OS/K8s patch management).

---

## Final self-check: did this pass reveal something new?

Yes, and honestly bounded. About three quarters of the corpus confirms canon and is not new; this
audit does not overturn the canon, and does not pretend to. The genuinely new material is real:
(1) the six-literature convergence as evidence for the composition thesis; (2) the counterexample
bank as a triple-convergent unbuilt artifact; (3) the undocumented concurrency/thread-safety blind
spot; (4) the `parts`-versus-`src` dependency that would make auto-evaluators misjudge the flagship;
(5) the polyglot claims lacking an in-repo evidence artifact; and (6) games-as-a-portfolio-category
being a total blind spot in the hiring literature. Those six change the engineering, the honesty of
the claims, or the positioning, which is the bar the audit set.

The actionable outcomes are tracked in `DEVELOPMENT_PLAN.md` under the 2026-07-28 Convergence section.
