# Convergence Review, Repeat Run (2026-07-17)

*The second Convergence Review (method: [../convergence_review.md](../convergence_review.md);
inaugural run: [2026-07-13-lemonade-board-review.md](2026-07-13-lemonade-board-review.md)).
Read-only. It finds the work; it does not do it. What to build, and in what order, is a human
decision.*

## Why now

The inaugural board (2026-07-13) ran when the ship "felt done." A great deal has shipped since:
the whole Chronicle (five record kinds plus retention R1), ARC completion and its Control
dimension, auth and secure-by-design hardening, GMCP, typed event frames (`parts/world/frames.py`),
the proving-ground `@arch preview` (`parts/foundry.py`), and proactive NPCs
(`parts/world/aggression.py`, PR #247, shipped the morning of this review). A large build spree is the
exact moment the doctrine says to re-run the board: a new capability "feels done" before a stranger
has ever exercised it.

Board: eight independent discipline seats (records/provenance, quality/observability,
safety/systems, security/AI-governance, human-factors/DX, knowledge-management/taxonomy,
architecture/vision/fleet, cross-disciplinary/unknowns), each reading the real system through its
own lens, blind to the others so convergence is a real signal and not an echo. Grounded first on
objective gate state: all local gates GREEN (lint, mypy strict, tests 1478 passed at 93.6 percent
coverage, bandit and secret scan clean); the one `forge-audit` FAIL was an offline artifact (the
dependency gate could not reach the CVE database and the collaboration probe was offline), not a
regression.

## Verdict

**STRONG PASS, ONE SYSTEMIC CONDITION.**

The machinery is senior-grade and every seat opened by crediting it honestly: a tamper-evident,
validate-on-read Chronicle; a tight, tested Foundry sandbox boundary; held auth hardening
(throttle-before-pbkdf2, constant-time decoy hash); one-door tick discipline intact under growth
(`forge.py` is 1609 lines and contains exactly one `elif`, the legacy ladder is gone). The
condition is not a defect in any one part. It is a pattern.

## The convergent finding (the strongest signal the method has)

> **The inaugural board's disease recurred in the newest build. "Capable core, orphaned last inch"
> is now systemic, not incidental.**

Seven of eight seats, each blind to the others, found the same shape in a different domain. A
finding that independent seats rediscover under different names is the review's highest-confidence
output.

| Seat | Where the last inch is orphaned | Cite | Verified |
|---|---|---|---|
| Records/Provenance | The Chronicle is an empty vault on `main`; every producer is human-run, none in CI | `chronicle/` (README only) | CONFIRMED |
| Quality/Observability | ARC `performance` checks that benchmark files exist, not that the tick got slower; a 10x regression stays green | `parts/arc.py:134` | CONFIRMED |
| Safety/Systems | The failsafe prevents death but creates a soft-lock; no disengage/leash; the multi-aggressor blast radius is uncapped | `parts/world/aggression.py:27` | CONFIRMED (design) |
| Security/AI-gov | The telnet codec is orphaned on the main input loop (login paths strip it, the game loop does not) | `parts/gateway.py:288` vs `:180,197` | CONFIRMED |
| Human-Factors/DX | An aggressive foe is not telegraphed; the `telegraph` part exists but combat does not use it; `look` takes no argument | `parts/world/npcs.py:41` | CONFIRMED |
| Cross-disciplinary | "Proactive" is a false label: the beat ticks only for the typing player, so idle and AFK players are immune | `forge.py:1577` | CONFIRMED |
| Architecture/Fleet | The feature is dark in every shipped game; `cinder_wight` (the aethryn boss) is the ideal empty call site | `seeds/*/npcs.yaml` | CONFIRMED |

The unifying mechanism (the doctrine's lens) is **quality-gating**: a capability is built, tested,
and filed, but nothing exercises or gates its last inch. The pattern is most concentrated in the
proactive-NPC slice shipped hours before the review, exactly the case the board exists to catch.

## Second-order findings (each a commit)

- **[HIGH] Cross-repo drift.** `DEVELOPMENT_PLAN.md` (in the sibling ship repo) still describes
  proactive NPCs as "the genuine unbuilt extension, a candidate future slice," denying a shipped
  feature (PR #247, `MOD-04.048`). Invisible to codeforge's own forward-claims ritual because no
  gate crosses the repo boundary. Mechanism: traceability.
- **[MED] Fleet single-source-of-truth.** Hash-chaining is four independent reimplementations
  (codeforge Chronicle, matrym-hashchain, ai-log-triage, federal-guidance-library). The published
  package is the only copy with HMAC authenticity and truncation anchoring; the security-critical
  copies (the Chronicle, audit trails) are the weakest and have no sync mechanism. Mechanism:
  traceability / single-source-of-truth. Partly by ADR-0002 design (harvest wins), so the real gap
  is that the package's safety improvements never flowed back to the copies that most need them.
- **[MED] Latent token-cost DoS.** The `ai` verb is player-rank and unthrottled (`forge.py:964`).
  Benign with the local brain, but the day `CODEFORGE_ARCHITECT=claude` is set on the public demo,
  any anonymous visitor drives unbounded paid Anthropic calls. Mechanism: quality-gating /
  governance.
- **[MED] Naming-standard self-violation.** `Foundry`, `Frame`, and `menace` are absent from
  `docs/naming_glossary.md`, which the naming standard requires before a name is adopted; AURA reads
  as a built subsystem in `docs/naming_standard.md:73` while it is honestly "planned, no code" in
  its home doc. Mechanism: standardization / documentation.
- **[MED] Frames pin the wrong invariant.** `render_for` ignores `viewer_id` and the test twin
  passes different viewers and asserts identical output, so the frame's reason to exist
  (per-recipient divergence) is documented, exercised nowhere, and certified the same. Mechanism:
  quality-gating (the gate proves the wrong invariant).
- **[MED] Gateway self-DoS and main-loop codec.** The HTTP LoginGuard has no forgive-on-success
  (an owner making rapid admin calls throttles themselves), unlike the telnet gateway; and the main
  game loop decodes without `_strip_telnet` (the codec is applied only on the login paths).

## The twelve-part output

1. **Blind spots.** No seat, and no test, owns "does the game actually play?" Every lens audits the
   machinery (records, quality, safety, security, DX, taxonomy, architecture) and the machinery is
   strong, but nothing verifies an end-to-end human play session (log in, walk the spiral, meet a
   hostile NPC, fall, recover). An interviewer running `codeforge play` is currently the only entity
   testing the product as a product.
2. **Missing disciplines.** Game design / balance economics. There is no `balance`, `economy`,
   `reward`, or `tuning` part; XP curves, damage, and now aggression are hand-tuned magic numbers
   with no telemetry on time-to-kill or death rate and no rubric for "is this fight fair." That is
   the seat that would have caught the aggression gaps on its own: you cannot balance an encounter
   that exists in zero games.
3. **Hidden assumptions.** (a) "The tick is the world's heartbeat" assumes a player is typing; an
   idle or AFK player is never menaced, and multiplayer aggression discriminates by keyboard
   activity. (b) "Dormant by default" hides that the feature is unexercised, not merely off. (c)
   Frames assume a future per-viewer consumer that does not exist yet.
4. **Cross-industry ideas.** Game-analytics and SRE shadow-traffic: record encounter outcomes (who
   struck whom, damage, ticks-to-resolution, death/restore counts) as typed events, then compute a
   balance report the way `pm status` computes the board. The same encounter ledger doubles as a QA
   regression signal and an anomaly feed, so it earns its place beyond the game.
5. **Better existing practices.** Statistical Process Control: the `metric` kind and `render_trend`
   exist, but the series is a table with no mean, control limits, sigma, or out-of-control rule. The
   SPC codebook is the mature practice the trend view half-implements.
6. **Fleet-level opportunities.** A one-part pilot of "adopt the published matrym-hashchain where
   authenticity and truncation matter" turns four drifting forks into one spine and gives the
   Chronicle real tamper-authenticity. A cross-repo correspondence check spans the ship/codeforge
   boundary that currently hides plan drift.
7. **Reusable Hardware Store components.** Primary harvest candidate: `foundry._resolve_in_sandbox`,
   a small stdlib sandbox-path-safety primitive that ai-log-triage (evidence bundles) and
   federal-guidance-library (change reports) both need as a shared "sandboxed writer" guard.
   Secondary: `parts/world/frames.py` is reuse-worthy but not shelved in the catalog.
8. **Blueprint updates.** The aggression feature shipped without a leash/disengage design; a
   Blueprint for "bounded hostile encounter" (leash, multi-aggressor cap, telegraph, failsafe as a
   hazard control not just a death preventer) would capture the FMEA the dormant switch currently
   lacks.
9. **Long-term technical debt.** `_build_commands` is a single ~1100-line function (router purity
   is intact, readability is not); `foundry._PENDING` is a per-process module global (approvals lost
   on restart, divergent across workers); the frames per-recipient seam risks becoming permanent
   speculative infrastructure.
10. **Future research.** Retention immutability versus a mandatory-erasure obligation (CUI spill,
    right-to-be-forgotten): an append-only hash chain and a must-destroy mandate collide, and the
    ship's federal posture makes this a real, unresolved question.
11. **What we have not thought of yet.** The flagship's cover story is a playable MUD, yet the
    proving ground has never proven itself by being played end to end under test. Green tests plus a
    dark feature reads as "shipped" at the engine tier while the content tier that exercises it is
    empty.
12. **The next capability to build (the next glass of lemonade).** Not another engine part. Make the
    newest capability real, safe, fair, and observed, and gate the pattern so it cannot recur.

## The recommended next build

The seats converged on one slice independently. It discharges the systemic condition and turns five
separate findings into standing infrastructure (the optimization ethos: do not merely list
problems, turn the solution into infrastructure).

1. Arm one **telegraphed** aggressive foe (`cinder_wight`, aethryn) in a room with an exit. Closes
   the dark-feature finding (six seats) and the fairness finding (DX).
2. Add an **aggression leash** and a **multi-aggressor per-tick cap**. Closes the soft-lock and
   uncapped-blast hazards (Safety).
3. An **end-to-end play smoke test** (login, move, provoked and unprovoked combat, fall, failsafe
   restore) driven through the tick. The missing "does the game play?" gate (Cross-disc,
   Architecture).
4. Record **encounter telemetry** to the Chronicle. Fills the empty vault (Records) and seats
   game-balance with evidence instead of a doc (Cross-disc).

A companion anti-recurrence step (deferred to its own decision): a **content-reaches-engine coverage
gate** (does any shipped seed exercise each engine capability?) and a **cross-repo correspondence
check** (does the ship plan still call a shipped codeforge MOD unbuilt?). These convert the last-inch
failure mode from a per-feature accident into a gated invariant.

## Method notes

Read-only board, eight seats, run as an Agent fan-out (the same method as the inaugural review). The
top seven findings were adversarially verified against the code before this report called them
CONFIRMED; the safety soft-lock is a design hazard confirmed by reading the loop, latent while the
feature is dormant. Honest accounting: the review found real gaps in work shipped hours earlier,
which is the board doing its job, not a mark against the build.
