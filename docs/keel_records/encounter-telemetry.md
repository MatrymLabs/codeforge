# Keel Record: Encounter Telemetry (the aggression loop's "observed" leg)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction design decision and its build slice. Per the doctrine, AI proposes and Josh
approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I learned"
reflection below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build (slice 1):** `parts/encounter_log.py` (a bounded, non-chained after-action log) wired into
  the tick at the four encounter beats, plus a read-only `encounters` verb.
- **Deferred (slice 2, same keel approval):** the trusted-boundary aggregate flush of the tallies
  into the Chronicle as one metric.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Give the aggression loop its "observed" leg (the 2026-07-17 Convergence Review's systemic condition
was "capable core, orphaned last inch"): make combat encounters visible and retained, so the world's
proactive behavior is not just felt but recorded and trendable.

## Problem
The Chronicle (`parts/chronicle`) is tamper-evident precisely because **every append comes from a
trusted (owner/CI) actor** (`arc_ledger.emit`, `bench --record`, `ai_eval`); there is no
player-reachable append path, and the Security seat praised exactly that. But encounters happen on
the **player tick** (`menace`, `_fall_and_recover`, `attack`). A per-encounter write from
`handle_command` into the hash-chained ledger would hand any player a write path into the trusted
store: the poisoning surface the design forbids.

## Constraints
- The Chronicle's "no player-reachable append" invariant is a **security boundary** and is not
  traded for a feature.
- The tick's telemetry store must be **bounded and ephemeral** (a flood rolls a ring, never grows
  without limit) and must **import nothing from `chronicle`** (a test pins this).
- Input validation fails loud: an unknown encounter kind or an empty `who` is a wiring bug, refused
  at the call, not logged as junk.
- Behavior preserved: recording is additive; no existing render or state changes.

## Decision (two layers, split at the trust boundary)
1. **Live layer (slice 1, this record):** `parts/encounter_log.py` -- a `CAP`-bounded in-memory ring
   of recent encounters plus running tallies by kind, written from the tick via `witness(kind, who)`.
   It is **not** the Chronicle: no hash chain, no evidence claim, no import of `chronicle`. A
   read-only `encounters` verb renders the ring + tallies. Wired at the four beats: `open_strike` and
   `leash_break` in `aggression.menace`, `fall` in `combat._fall_and_recover`, `defeat` in
   `combat.attack`.
2. **Retained layer (slice 2, deferred):** a trusted boundary (an owner command / `make daily`) reads
   the tallies and records **one aggregate `metric`** into the Chronicle via the existing
   `record_metric`/`trend` machinery -- never per event, never from the tick. The player never
   triggers a Chronicle append; a summary count does, at a boundary Josh controls.

## Alternatives considered
- **Rate-limited player writes into a Chronicle `encounter` kind** -- *rejected.* Even throttled, it
  gives the player a write path into the tamper-evident ledger, dilutes "trusted append-only," and
  grows the ledger with per-event noise. It kills the exact property Security praised.
- **Live layer only** -- loses the retain/trend memory that is the Lemonade finding's whole point.
- **Aggregate only** -- loses live observability ("what just happened").
- **Two-layer (chosen)** -- observability + retained trend, the security invariant fully intact, and
  it *reuses* the Chronicle instead of extending its threat surface.

## Tests / evidence
`tests/test_encounter_log.py`: unit (witness/recent/tally/render), bounds (a `CAP+50` flood rolls the
ring to `CAP` while the tally still counts every beat), refusals (unknown kind, empty who), the
**security invariant** (no `chronicle` import), verb reachability through `handle_command`, and wiring
proof (felling a foe witnesses a `defeat`; an aggressive open-strike witnesses an `open_strike`).
`make check` green; filed MOD-10.035 + CMD-04.066, `make readiness` clean.

## What I (Josh) learned
*(left for Josh: e.g. trace an encounter from `menace` -> `witness` -> the ring -> the `encounters`
verb; name why the tick may write the ring but never the Chronicle; predict what slice 2's aggregate
metric would show after a session of combat.)*

## Final decision / review point
Slice 1 ships the live layer behind the full gate. Slice 2 (the aggregate flush) is the same keel
approval but a separate PR, to be built once the live layer is in. Revisit if a game ever needs
per-player (not world-scoped) encounter history, or persistent-death changes what "defeat" means.
