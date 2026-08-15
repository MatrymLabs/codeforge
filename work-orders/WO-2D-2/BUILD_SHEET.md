# WO-2D-2 BUILD SHEET

**Repo:** `codeforge`

## Scope

`codeforge` only. `kernel/world/session.py` and its tests. **The 123 consumer call sites are not in
scope and must not need editing.** If one does, the design is wrong and that is the finding.

## Invariant

**Behaviour is identical under Engine-0D, and the suite proves it by passing unchanged.** This
order puts the engine in the path; it does not change what the path returns. A test edited to
accommodate this change is evidence the change altered behaviour, not evidence it works.

```yaml
packet_id:            WO-2D-2
title:                Put the engine in the path: Session.position, derived location
stream:               engine
repository:           codeforge
goal: >
  D8 stage 2D-2. Today the Engine Protocol has no consumer outside its own file, so the
  differential compares two objects the core never uses. This wires it in.

  Session gains `position`, engine-native and opaque, produced by `engine.place(room)`. Session
  keeps `location`, but it becomes DERIVED: `engine.room_of(self.position)`, still a string, still
  a room label. Assignment to `location` routes to `position = engine.place(room)`.

  RESIZED 2026-08-14 on WO-2D-1's evidence, which is why this is smaller than it first looked.
  The scout classified all 123 references: 94 room-label consumers, 8 assignments, 21 "genuine
  position queries". Six of the 21 were spot-checked and every one is a room-label EQUALITY
  COMPARISON, which a derived property returning the same string satisfies unchanged. So the
  expected consumer churn is ZERO.

out_of_scope: >
  Do NOT edit the 123 consumer call sites. If a consumer needs changing, STOP and file BLOCKED:
  either the design is wrong or the scout mis-bucketed a site, and both are findings rather than
  edits.
  Do NOT make Engine-2D real: no spatial index, no movement resolution, no renderer.
  Do NOT change what is persisted. character_store stores a room label and must continue to.
  Do NOT touch the differential battery, its probes or the saboteurs; 2D-3 owns those.

file_allowlist:
  - kernel/world/session.py
  - tests/test_session.py
  - tests/test_engine_seam_differential.py

blast_radius: |
  From WO-2D-1's report, reports/2026-08-14-seam-surface-scout.md on origin/main:

    room-label consumer      94     unaffected: they read a room label and still get one
    assignment                8     routed through engine.place()
    genuine position query   21     of which six were spot-checked and are all equality
                                    comparisons on the label, which survive unchanged
    total                   123

  $ grep -rn 'Session(' --include=*.py kernel/ adapters/ forge.py tests/ | grep -c 'location='
  186        construction sites passing location= by keyword

  The 186 constructors are the real risk and are why `location` must remain ACCEPTED as a
  constructor argument. A design that forces 186 sites to pass `position=` has moved the problem
  rather than solved it.

  THE SEVEN THAT CROSS A BOUNDARY, named by the scout and worth reading before you start: the
  CharacterRecord persistence, the protocol `num` field twice, the restart-parity snapshot, the
  cross-process room-change baseline, the `room:` item-resolution scope string, and the navigation
  start node. All seven still work if `location` returns the same string. They are where the label
  ESCAPES the process, so they are where a non-string position would eventually hurt.

boundary: >
  This order OWNS kernel/world/session.py and the two test files. It reads the 27 consumer files to
  confirm they still work and edits none of them.

  kernel/engine_seam.py is NOT in the allowlist. The Protocol already exists and is the contract:
  consume it, do not define a second one. If a default-engine accessor is genuinely required to
  make `location` derivable without threading an engine through 186 constructors, that is a
  finding to report, not a file to open.

  character_store is NOT in the allowlist and needs no change; it persists a room label and must
  keep doing so. If persistence must change, the order is BLOCKED.

preconditions: >
    CHECK: file kernel/world/session.py contains location
    CHECK: file kernel/engine_seam.py contains room_of
    CHECK: file reports/2026-08-14-seam-surface-scout.md exists

    Behavioural:
      Read the scout report first. It names the seven boundary-crossing sites, and knowing them
      before you start is the entire reason WO-2D-1 ran ahead of this order.
      export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
      make proto && make check                                    exit 0 before you start

contract_tests:
  - tests/test_session.py
  - tests/test_engine_seam_differential.py
  ASSERTION-LOCKED across the WHOLE suite, not only these two. The proof of this order is that
  every existing test passes UNCHANGED. If an assertion has to move anywhere, stop and file
  BLOCKED: you have changed behaviour, and this order is defined as the change that does not.

definition_of_done:
  - "Session carries `position`, engine-native, produced by engine.place()."
  - "Session.location reads through engine.room_of(position) and still returns a room label string."
  - "Assigning to Session.location routes to position = engine.place(room)."
  - "`Session(location=...)` still works at all 186 construction sites, unedited."
  - "character_store persists and restores a room label with NO change to that module."
  - "THE PROOF: the entire suite passes with no test edited, and `git diff --stat` touches only the
     three allowlisted files."
  - "THE TEST THAT DECIDES THE ORDER: substitute an engine whose room_of returns a DIFFERENT valid
     room, and assert session.location FOLLOWS it. If it does not, the engine is not in the path
     and the wiring is decorative, which is the exact failure 2D-4 exists to catch. A test that
     merely checks `position` exists would pass while proving nothing."
  - "make proto && make check green."

verification_command: |
  cd codeforge && make proto && make check && git diff --stat origin/main...HEAD

rollback: >
  git revert. Session returns to a plain string field and every consumer is unaffected, because
  none was edited.

approval_gates: >
  A BLOCKED return is expected and welcome if a consumer turns out to need editing. That is a
  Principal Engineer decision about the domain model, not a Bench repair.

size:                 medium

taint_class:          SAFE

# EXTRACTION CONTEXT
store_search_result: >
  Certified Tier (hardware-store/catalog/): searched for a derived-attribute, value-object or
  position-abstraction Part. Nothing catalogued. Working Shelf (codeforge/catalog/parts.yaml):
  searched the same; PRT-0006 typed-settings is the nearest shape and governs configuration rather
  than domain identity. BOTH tiers searched, both empty.

parts_to_consume:     the Engine Protocol in kernel/engine_seam.py. It is the contract already.

watch_for: >
  Whether a module-level default engine is needed to derive `location` without threading an engine
  through 186 constructors. If it is, say so plainly in the Bench Report: a module-level singleton
  is a real architectural cost and belongs in the open, not buried in a diff. It may be the right
  trade at this stage, but it is the Principal Engineer's trade to accept.
```

## The stage after this one is allowed to fail

2D-4 re-measures the falsifiability count, today 3 of 14. **If it does not rise well above that,
this wiring is decorative and gets reverted rather than reported as progress.** That is written
into D8 deliberately: two seam criteria have been authored that could not fail, both found only
after the work, and a stage whose failure is pre-authorised is the only kind that reports honestly.
