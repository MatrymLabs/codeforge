# AGENTS.md - codeforge

the flagship: a Python-native multiplayer MUD engine and self-auditing engineering stack.

<!-- MATRYM:DOCTRINE:BEGIN - synced from ship docs/AGENTS_DOCTRINE_BLOCK.md. Do not edit here. -->

## Required Reading

Before any work, every session, read these in order and confirm by stating one line from each.
**They are canonical at the WORKSHOP ROOT, one directory above this repository**, because this repo
is a separate git repository and does not contain them.

| # | file | what it carries |
|---|---|---|
| 1 | `../MATRYM_WORKSHOP_CANON.md` | the single active Workshop doctrine. Nothing else governs |
| 2 | `../.ai/HANDOFF_PROTOCOL.md` | how the two Benches exchange work under the canon: Build Sheet and Bench Report schemas, the pattern screen |
| 3 | `../.ai/WORKBENCH.md` | the live operating surface. The Active Build is at the top. Read at open, update at close |
| 4 | `../.ai/WORK_REGISTER.md` | one row per Work Order, from dispatch to landing |
| 5 | `../BUILD_STATE.md` | generated: the Line and the Bench Claim board. Never hand-edited |
| 6 | **this file** | stack, gate command, and repo-specific context |

**Precedence.** 1 is the doctrine. 2 is how the Benches exchange work under it. 3, 4 and 5 are
state, never doctrine. Where anything conflicts with 1, 1 wins: flag the conflict, do not resolve
it yourself.

**Retired 2026-08-13 by WO-WORKSHOP-CANON-001**, now compatibility pointers and never authority:
`WORKSHOP_DOCTRINE.md`, `ENGINEERING_MANUAL.md`, `ENGINEERING_IDENTITY.md`, `MISSION.md`,
`MATRYM_LABS.md`, `SHIP.md`, `FLEET_ARCHITECTURE.md`, `FLEET_ENGINEERING_STANDARD.md`,
`MATRYM_NORTH_STAR.md`, `TRUE_NORTH.md`, `.ai/CHIEF_ENGINEER.md`, `.ai/GREEN_BUILD_DIRECTIVE.md`,
`.ai/ONE_FLEET_ONE_FLIGHT.md`, `.ai/RELAUNCH_SEQUENCE.md`. Do not cite any of them and do not
reintroduce their operating language.

**If you cannot read the canon, say so and stop.** Do not proceed on assumed context. The
non-negotiables below are restated so this repo is not silently ungoverned when the Workshop root
is out of reach, but they are a summary and never a substitute.

## Non-negotiables

- **Completion Law** - done means the Proof Run command ran *this session* with its output in the
  Bench Report. Prior reports, READMEs, commit messages and comments are **claims**, not evidence.
- **Verification Duty** - the receiving Bench reruns the other's Proof Run. A Bench Report is input
  to verification, never a substitute for it.
- **Verify against origin, not against your own checkout.** Record
  `git rev-list --count HEAD..origin/main` and its result. Zero, or it is not a Proof Run of the
  current tree.
- **The whole instrument, never a subset.** A green local run is not a green CI matrix.
- **Failure before repair.** Repair-and-report is forbidden. Run, capture the failure, report the
  failure verbatim, repair, run again, record both.
- **Consume first.** Search the Hardware Store before implementing any capability and log the
  search: the Certified Tier (`hardware-store/catalog/`) FIRST, then the Working Shelf
  (`codeforge/catalog/parts.yaml`). A log showing one tier is an incomplete search, not a complete
  one that found nothing.
- **No self-certification.** The R&D Tech Lab's Verdict Gate is the only path into the Store, and
  no Bench certifies a Part it authored.
- **A Gate is trusted only when it has been shown to fail** for the bad state it claims to catch.
  An instruction that cannot fail is decoration.
- **One Work Order, one PR.** Never combine. Never fix things outside the Work Order; file them.
- **Non-destructive.** No deletes, resets, force-pushes, lockfile rewrites or migrations without an
  explicit Principal Engineer ruling.
- **A branch is CURRENT with `main` before it merges.** CI answers "is this branch green against
  the main it was cut from", never "is the merge RESULT green".
- **Secrets never enter git**, passwords are never stored or logged in plaintext, and secrets are
  never case-mangled: routing may normalise command text, but secret-bearing input is parsed from
  the ORIGINAL.
- **No em-dash or en-dash glyphs** anywhere: prose, code, comments, commit messages, command
  output. This is a Workshop HARD RULE and it is interviewer-facing.
- **The Principal Engineer decides what lands.** Josh holds the standing merge grant and its terms;
  an agent unsure whether something breaks has already answered.

## Reusable Part signals

Every Bench Report carries four signals and none may be left blank. "None observed" is valid;
silence is not.

```yaml
reimplemented:
recurrence:
generalizable:
friction:
```

First occurrence of a mechanism is logged only. **Second** occurrence opens a reusable Part
candidate, and certification becomes meaningful at the second real consumer, because duplication is
cheaper than the wrong abstraction. Promotion travels the Verdict Gate; there is no second path.

## Before you touch a file

Read `../bench-claims/CODEX.yaml` and `../bench-claims/CLAUDE_CODE.yaml`, and record your own Bench
Claim in your own file. Neither Bench edits the other's. `make claims` at the Workshop root refuses
a board where two active claims from different agents own overlapping paths.

**Then prove you are in your own tree:**

```bash
cd ..  &&  MATRYM_AGENT=<your-agent-id> make worktree     # the guard lives at the Workshop root
```

`../worktrees.yaml` maps each agent to its trees. The guard refuses a tree that is not yours,
refuses a destructive command that would touch uncommitted work outside your active claims, and
refuses an agent it does not recognise rather than guessing. The Bench Claim board guards PATHS;
this guards the TREE, and the two are not the same control. On 2026-08-10 a `git stash` in a shared
checkout moved another agent's uncommitted claim, and it survived on timing alone.

**Then state it:** *"Active Build: X. My Bench: Y. This session serves it by: one sentence. Owned
paths: the Bench Claim. Drift check: clear, or the condition."* If that sentence cannot be said
honestly, report the drift instead of starting work.

<!-- MATRYM:DOCTRINE:END -->

## The gate

```bash
cd /home/josh/Projects/MatrymLabs/codeforge
export PATH="$PWD/.venv/bin:$PATH"
make check
```

**Bare `pytest` and `python3 -m pytest` do NOT work on this host.** The venv must be on PATH, or
pass an interpreter explicitly with `make check PY=/path/to/python`.

## Conventions

- Conventional Commits, ending with the required `Co-Authored-By` trailer.
- Branch, PR, CI green, merge. Never commit to `main`.
- No em-dash or en-dash glyphs anywhere: prose, code, comments, commit messages, or command output.
  This is a fleet HARD RULE and it is interviewer-facing.
- A gate must be able to fail. If you add a check, prove it red before you trust it green.
