# Lemonade Protocol: Interdisciplinary Board Review

- **Date:** 2026-07-13 (day 194)
- **Type:** multidisciplinary gap analysis (the Lemonade Protocol / Expansion Review)
- **Method:** a six-seat interdisciplinary review board, each seat reading the live
  codebase through one discipline's lens, then synthesized against the research.
- **Grounding research:** *"Multidisciplinary Coding Practices Since 2019"* (a
  deduplicated review of coding-practice families across qualitative research, clinical
  coding, data annotation, records management, software engineering, MLOps, and low-code).
- **Scope:** read-only review. No code changed. Recommendations are staged for approval.

## Why this review exists

The research's central finding is, almost verbatim, this ship's founding thesis:

> Many "different" coding practices are really the same workflow logic wearing different
> professional outfits. The biggest unresolved problems are not the invention of brand-new
> practices; they are the transfer of mature practices across domains, clearer evidence on
> when a practice works, and better integration of practices studied in isolation.

That is the optimization ethos (`docs/optimization_ethos.md`) and "multidisciplinary by
design" confirmed by peer-reviewed literature. This review operationalizes it: transfer
mature ideas from disciplines the builder already holds (records management, Lean Six
Sigma, instructional design, USAF systems/safety) into CodeForge.

The research names five gaps to grade any system against: (1) taxonomy by **mechanism**,
not label; (2) **effectiveness** evidence (when does a practice work, for whom, under what
constraints); (3) **cross-artifact integration** (govern code + data + models + notebooks +
environments + metadata + deployment state as one whole); (4) **human factors &
accessibility**; (5) **AI-assisted-coding governance** (AI as a modifier of existing
families, not a separate universe).

## The finding the board reached together

Five of six seats, blind to each other, hit the same root:

> **CodeForge is a world-class conformance-and-construction machine that computes and
> renders the present moment brilliantly, then throws it away. It proves *now*; it does
> not *retain, relate, or measure over time*.**

Evidence is git-ignored. Metrics are rendered then discarded. Change, incident, and
learner records live in memory only. AI is evaluated once, never tracked. Artifacts are
islands, not a graph. The ship's own ethos names the missing step: *Build to Observe to
Measure to ... to **Measure Again*** and the "Measure Again" is the unbuilt half.

A second, tactical pattern recurred: **the ship builds a capable engine and aims it at the
wrong target.** The bake-off harness points at `slugify`, not the LLM it could govern.
`change_ledger`'s lifecycle is never persisted, so it cannot be the incident register or
the change archive. Dated reports are written and never read back. The Hardware Store's
`domain` list is a mechanism taxonomy in embryo, stopped at 16 parts. Nearly every
recommendation below is "aim the gun you already own."

## The board (six seats, one root)

| Seat | Found the ship... | Missing organ |
|---|---|---|
| MLOps / AI-governance | evals AI once, never over time | eval-regression memory |
| Lean Six Sigma / SRE | renders a metric, discards it | trend series (SPC) |
| Records / provenance | computes evidence, git-ignores it | provenance graph |
| Safety / systems | borrows safety words, not the machines | FRACAS + FMEA records |
| Human factors / a11y | good instincts, un-gated | usability/a11y gate |
| Taxonomy / KM | classifies by type + domain, not mechanism | mechanism facet |

## 1. Blind spots (ranked by fleet leverage)

1. **B1 - No retained, linked memory.** Evidence git-ignored (`security-evidence/`,
   `arc-evidence/`, `reports/*`, the SBOM); `ChangeLedger` uses `InMemoryRepository`;
   artifacts are islands with no traceability graph (blueprint to part to test to evidence
   to verdict to change to release exists only in prose).
2. **B2 - AI output quality is ungoverned over time.** Prompts (`_DRAFT_SYSTEM`,
   `_ARCHITECT_SYSTEM`) are untested inline literals; no eval set; model id hardcoded twice
   with no drift alarm; no model card.
3. **B3 - No mechanism axis.** The registry classifies by TYPE + DOMAIN; the ship cannot
   list "every quality-gate" or "every traceability mechanism" (the research's #1 rec).
4. **B4 - No outcome/trend measurement.** Only point-in-time verdicts; a latent time-series
   sits in dated `reports/` and nothing reads it; no SLO or error budget.
5. **B5 - No usability/accessibility gate.** a11y asserted by hand; `forge-audit` has zero
   human-factors axis; the Classroom's ADDIE "Evaluate" loop is unbuilt (learner progress
   is in-memory).
6. **B6 - Safety formalisms are vocabulary, not machines.** No structured FMEA/RPN, no
   FRACAS-to-closure, no requirement-to-test traceability. The building blocks all exist.
7. **B7 - Truth-discipline gap.** `reuse_score` is a hand-entered int with no VeritasGate,
   unlike every other claim on the ship.

## 2. Missing disciplines (and why)

Of the research's ~25 practice families, CodeForge covers most at a senior level.
Genuinely absent or un-gated: **MLOps** (AI-governance for its own AI, nascent only),
**Accessibility** and **Human Factors** (instinct, no gate), and the **temporal face of
Observability / Provenance / Traceability** (retention and trend). The absence is coherent:
the ship optimized for proving correctness at a moment (its portfolio thesis), which
structurally under-weights memory, outcomes, and usability - the exact axes the literature
says the whole field under-measures.

## 3. Hidden assumptions (never questioned)

- "If the gate is green, the work is good." Conflates conformance with effectiveness.
- "Evidence is regenerable, so it needn't be retained." True for reproducibility, false for
  audit/provenance ("what proof justified release v0.1.0?" is unanswerable today).
- "AI is governed because a human approves it." Governs authorship, not output drift.
- "Classification is type + domain." Misses mechanism, the axis that exposes reuse.
- "Usable because it's correct." The human-factors fallacy the research names head-on.

## 4. Cross-industry ideas to borrow

- **W3C PROV-O** (provenance graph) + **SLSA/SBOM retention** - the one graph B1 needs.
- **NARA retention and disposition schedules** - make CLAUDE.md's Federal Rule #10 code.
- **SPC control charts + SRE SLO/error budgets** - a governed target, not just a number.
- **MLOps prompt-registry + LLM-as-judge regression + model card** - drift alarms.
- **FMEA/RPN + FRACAS-to-closure** - structured risk, incidents tracked to verified closure.
- **SKOS / ISO 25964 thesaurus + Ranganathan faceted classification** - collapse the
  forge-voice synonym rings (Gate / gate / QualityGate) onto mechanism concepts.
- **WCAG 2.2 AA / axe-core gate** - enforce the good a11y instincts.

## 5. Better existing practices (keep, sharpen)

Do not touch, just extend: fail-loud gates (textbook poka-yoke); ARC's "MISSING is never a
pass"; VeritasGate refusing uncited claims; the injected-client AI seam; the blameless
postmortem template; the ritual's gated phases; and a TYPE/DOMAIN registry the taxonomy
seat called "the best-organized I've seen in a portfolio repo." Every lemon below is
additive, never a rewrite.

## 6. Fleet-level opportunities

Every top lemon generalizes across all three repos: a retained provenance/trend ledger
(codeforge registry + FGL `source_registry` + ai-log-triage `compliance/` evidence); a
mechanism vocabulary `forge-audit` scores every repo against; a retention-schedule part; a
FRACAS register (all three have the "when it fails, where is the record?" gap).

## 7. Reusable Hardware Store components (the harvest)

- **`chronicle` / `provenance_ledger`** - append-only, hashed, PROV-O-shaped store the ship
  reads back (the keystone; see section 12).
- **`trend_series`** - metric points to run/control charts + drift (a record type on the chronicle).
- **`incident_register`** (FRACAS) - `change_ledger` re-skinned to
  identified to analyzed to corrective to verified to closed.
- **`fmea`** - typed `{mode, S, O, D, RPN, mitigation, verified_by}` with a loud gate.
- **`thesaurus`** (SKOS-lite) + **`facet_index`** - mechanism vocabulary + multi-facet query.
- **`a11y_gate`** - one HTML-projection accessibility checker, fleet-wide.
- **`reuse_counter`** - walks the import graph; makes `reuse_score` computed and VeritasGate'd.
- **`retention_schedule`** - record-type to retention/disposition/hold; refuses purge under hold.

## 8. Blueprint updates

- Upgrade the Blueprint security field (shipped this session) to structured FMEA rows +
  per-requirement `verified_by` test refs; add QG06 (a validated blueprint has zero
  unmitigated high-RPN modes and no orphan requirements).
- New Blueprint: "The Chronicle / Provenance Spine" (the keystone).
- New Blueprint: "Mechanism Taxonomy Overlay."
- New Blueprint: "AI Output Governance Gate" (`make ai-eval`).
- New Blueprint: "Human-Factors / Accessibility Gate."

## 9. Long-term technical debt

Duplicated model id (two sources of truth); `performance_gate.md` baselines as hand-typed
prose (drift trap); two disconnected "learning" systems (`learning_record` vs `classroom`);
two disconnected vocabularies (registry DOMAIN vs Hardware Store `domain`);
`naming_glossary` as a word list not a thesaurus; the ritual's flown checklist discarded.
All are "built twice, or the record is not kept."

## 10. Future research opportunities

The research's own open lanes, answerable here with evidence: "when does a practice work,
for whom, under what constraints" (effectiveness); cross-artifact reachability; and
AI-assisted-coding-governance benchmarks on a live, non-synthetic corpus - CodeForge could
*be* that corpus (it is AI-built with full provenance). A genuine research contribution
hiding in the repo.

## 11. What we haven't thought of yet

The board's blind-to-itself insight: **the ship has a `tick` (a present) but no
`chronicle` (a past).** `handle_command` is the engine of *now*. There is no symmetric
engine of *memory* the ship consults to answer "how did we get here, is it getting better,
and can we prove it?" That asymmetry is why five seats independently found
compute-and-discard. Naming it collapses the whole gap analysis to one missing organ.

## 12. The next glass of lemonade

**Build the ship's memory: a retained, append-only, hashed, linked `Chronicle`** - the
symmetric twin of the tick. One append-only store with typed records (evidence bundles,
metric points, incidents, AI-eval scores, provenance edges) that ARC and `forge-audit` read
back. It is the keystone the board converged on because it simultaneously:

- gives `change_ledger` / `release_gate` / an incident-register their persistence;
- flips ARC's change / patch / release / evidence dimensions from honestly-MISSING to
  actually-filed (completing the "Complete the Ten" ARC work deferred this session);
- hosts the trend-series (Six Sigma) and eval-regression memory (MLOps) as record types;
- retains evidence instead of git-ignoring it (records + safety);
- and is the research's #1 ask (provenance as core infrastructure) and #3 (cross-artifact
  integration) in one move.

The mechanism taxonomy (B3), AI-eval (B2), and a11y axis (B5) are the three next glasses;
each upgrades a scoring tool (registry / bake-off / forge-audit) and turns one of the
builder's credentials into gated evidence. Design for the Chronicle is filed alongside this
review; the implementation awaits sign-off (a core-architecture critical junction).
