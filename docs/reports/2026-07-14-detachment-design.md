# Design for Sign-Off: Engine Detachment (vendored-whole -> vendored-selective)

- **Date:** 2026-07-14 (day 195)
- **Status:** DESIGN - awaiting Josh's sign-off. No engine code changed. This is the vision's #1
  architectural-risk item (`vision_resync.md`) and a core-system change, so per the human-keel
  doctrine and the vision's own approval gates it stops here for a keel decision.
- **Origin:** the last remaining rung of staircase step 4 (package export). A cast now assembles,
  runs, and runs in a fresh isolated venv - but it still vendors the WHOLE engine.

## Problem (one sentence)

A cast vendors all 121 `parts/` modules whole (`engine_strategy: "vendored-whole"`), so every
shipped game carries the self-auditing engineering stack, the admin/API/CLI surfaces, the
manufacturing tooling, and the compliance library it never runs - the monolith the vision named
as its deepest risk.

## The evidence (measured today, honestly caveated)

An import trace (boot `forge`, then drive a spread of real game commands: look, help, score,
inventory, movement, combat, quest, catalog, workshop) loaded **69 of the 121** modules. The other
**52 never loaded** on that path - candidates to detach:

> ai_eval, api, architect, assembly, bench, blueprint*, cast, chronicle, cli, config, console,
> dashboard, db, dependencies, exporters, foundry, frameup, gateway, integrity, law, library,
> login_guard, loop, manifest, onboarding, patch_tracker, pm, qualitygate, regulations,
> release_gate, reporting, retention, terminal, veritas, web_gateway, ... (52 total)

**Honest caveat (the crux):** that trace *under-counts* the true runtime set. The command spread
did not exercise every mode, so the 52 include modules that ARE needed for surfaces I did not
drive: `db` (save/load), `gateway`/`web_gateway` (multiplayer), `login_guard` (auth),
`terminal`/`config` (solo play + settings). **Detachment is therefore NOT "exclude the 52."** The
sheddable set depends on which surfaces a cast is meant to support, and a wrong exclusion breaks a
mode the single-tick `validate_cast` would never catch.

## Proposal: a validation-gated, phased detachment

Three phases, each smaller and safer than a monolith rewrite; D2 and D3 each need their own keel
sign-off.

- **D1 - the coupling report (read-only, recommended first).** A `parts/coupling.py` analyzer that
  computes the runtime module closure by TRACING imports across a command corpus per surface
  (solo, +save, +multiplayer, +admin), classifies each `parts/` module as **runtime-core /
  surface-optional / dev-only**, and reports the detachable candidates with the coupling that
  blocks a clean cut (a dev module a runtime module imports). It changes NO vendoring - it produces
  the evidence D2 needs and makes the risk visible. This is inspection/mapping (in-latitude).
- **D2 - selective vendoring (keel).** `generate_cast` vendors only the closure for the cast's
  chosen surfaces (`engine_strategy: "vendored-selective"`), gated by a BROAD validation harness
  that exercises every cast command (not one tick), so a missing module fails loud at generation.
  Needs D1's closure and the harness to be trustworthy first.
- **D3 - true decoupling (keel, deepest).** Interfaces/plugin boundaries between the runtime core
  and the optional subsystems (engineering stack, compliance, manufacturing), so they are selected,
  not sheared. Only if D1/D2 show the seams are real.

## Architecture-law compliance

1. State canonical; text a projection - the analyzer READS and reports; it never mutates.
2. Reproducible - the closure is computed from the code at a commit, re-runnable.
3. Fail loud - D2's harness fails generation if a selected surface's command loses a module.
4. No claim without correspondence - `engine_strategy` stays `vendored-whole` until D2 actually
   ships selective vendoring; the manifest never claims a cut it did not make.

## Alternatives considered

- **Stay vendored-whole.** Rejected as the end state (it IS the named risk), but it is a perfectly
  honest INTERIM - a cast that assembles, runs, and installs in isolation is already a real export.
  Detachment is optimization, not correctness; do it on evidence, not pride.
- **Static AST import graph only.** Rejected as the sole method: the engine imports lazily inside
  functions, so a static graph both misses runtime edges and over-lists dev-only ones. D1 must
  TRACE real imports across a command corpus, not just parse `import` lines.
- **Naive "exclude the non-game list."** Rejected: it breaks save/multiplayer/auth/solo, and the
  one-tick validate would not catch it. This is the trap the caveat above exists to prevent.

## Security, risks, rollback

- **Risk:** shedding a module a mode needs. Mitigated by making D1 read-only and D2 gated by a
  per-command validation harness; nothing ships selective until the harness is trustworthy.
- **Security:** a smaller cast has a smaller attack surface (fewer modules, no admin/API/compliance
  in a solo game) - a benefit, once the cut is proven safe.
- **Rollback:** D1 is additive and inert. D2 keeps `vendored-whole` as the default strategy; a cast
  opts into selective. No engine architecture changes until D3, its own separate decision.

## The keel question for Josh

1. **Approve D1** (the read-only coupling report) as the first step? It builds the evidence and
   makes the risk visible with zero change to how casts are poured. (My recommendation: yes.)
2. **What surfaces should a cast target?** solo-only (smallest), +save, +multiplayer, +admin? This
   decides the closure D2 would vendor and can wait until D1's report is in hand.
3. D2 (selective vendoring) and D3 (true decoupling) each return for their own sign-off - do NOT
   treat this doc as approval for either.

**Approve D1, adjust it, or redirect.** Vendored-whole is an honest interim; detachment proceeds
only on measured evidence and a keel decision, never on intuition.
