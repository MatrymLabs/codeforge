# Bench Report: WO-REV-SELFPROOF

## Verdict

ACCEPT. The fix was reviewed on `fix/exec-bit-cast-selfproof`; no source changes were made by
this review.

## Adversarial answers

1. **Persist runs on every invocation.** A first run passed. I then renamed `def save_character`
   to `def save_character_removed` in the poured product and ran the proof again. The repeat
   exited 1 with `REFUSED: AttributeError: module 'kernel.world.characters' has no attribute
   'save_character'`. This proves the second invocation reached persist; a marker-only shortcut
   would have passed before importing the renamed function.

2. **Both original refusals remain intact.** Removing the persisted database produced:
   `REFUSED: persisted database is missing: codeforge.db` and exit 1. Corrupting the persisted
   `level` field produced `REFUSED: persisted field mismatch: level: expected 7, got 99` and exit 1.
   These are runtime refusal paths, not weakened assertions. The target test suite reported
   `3 passed in 1.10s` under `.venv/Scripts/python.exe -m pytest tests/test_cast_selfproof.py -q`.

3. **The marker/database mismatch pre-check is reachable.** After an initial pass I corrupted the
   database and reran with the prior marker. The run returned the mismatch refusal above, while a
   recorded spawn trace was exactly `SPAWN_STAGES= ['restart']`; persist was not reached and could
   not overwrite the evidence.

4. **No newly passing bad case found.** The repeat sabotage, missing database, and mismatch cases
   all refused before a false PASS. The full target-branch check also passed. No defect was found.

## env-parity review

`BLOCKING_KINDS = frozenset({"exec-bit-divergence"})` is at the final verdict boundary: the report
still prints every finding, advisory findings still return 0, and an exec-bit finding returns 1.
The real target run returned 0 with 18 advisory extras-drift findings. A controlled report with one
advisory and one `exec-bit-divergence` returned 1, proving the boundary fails for the claimed bad
state.

## Proof runs

- `.venv/Scripts/python.exe -m pytest tests/test_cast_selfproof.py -q` -> `3 passed in 1.10s`.
- `make env-parity` -> exit 0; advisory drift printed, no blocking finding.
- `GOFLAGS=-buildvcs=false make check` on the target branch -> exit 0; `5431 passed, 58 skipped,
  1 xfailed`, coverage `93.37%`.

The bare `python -m pytest ...` command was not evidence on this Windows bench: its interpreter
did not know the repository's `timeout` option. The repository venv command above is the valid run.

## Pattern screen

- Lane echo: persistence, commands, events, transactions, world graph, and integration were
  screened; the marker-before-persist ordering and restart evidence are consistent with that lane.
- Catalogue match: none found in Certified Tier or Working Shelf for this self-proof capability.
- Recurrence check: the detached proof repeats the Workshop's persistence/restart evidence pattern;
  no separately carded reusable Part was consumed.
- Verdict note: none observed beyond the existing proof shape; no Part is self-certified.

## Reusable Part signals

- **reimplemented:** none observed.
- **recurrence:** persist/restart/survive and sabotage refusal recur as a product-proof pattern.
- **generalizable:** pre-check prior evidence, persist unconditionally, then record fresh evidence.
- **friction:** the required test command needs the repository venv on this Windows bench; bare
  Python collected no tests because its pytest configuration differed.

## Awaiting Principal Engineer

Review recommendation: ACCEPT. No source defect or merge decision is requested from this report;
the Principal Engineer still owns final approval and merge.
