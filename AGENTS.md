# AGENTS.md - codeforge

the flagship: a Python-native multiplayer MUD engine and self-auditing engineering stack.

## Required Reading

Before any work, every session, read these four in order and confirm by stating one line from each:

1. **`MATRYM_NORTH_STAR.md`** - the mission and the Law. What the fleet is and why it is one machine.
2. **`.ai/HANDOFF_PROTOCOL.md`** - the rulebook of exchange between Claude Code and Codex: roles,
   artifact schemas, the Verification Duty, extraction capture, standing rules. Does not change per
   packet. Read it; never edit it without founder approval.
3. **`.ai/handoff.md`** - the live board: what packet is in flight, what is blocked, what awaits
   founder action. Read at session start; **update at session end.**
4. **This file** - stack, gate command, and repo-specific context.

**Where those three live.** They are canonical at the FLEET ROOT, one directory above this
repository, because this repo is a separate git repository and does not contain them:

```
../MATRYM_NORTH_STAR.md
../.ai/HANDOFF_PROTOCOL.md
../.ai/handoff.md
```

**If you cannot read them, say so and stop.** Do not proceed on assumed context. The
non-negotiables below are restated here so this repo is not silently ungoverned when the fleet
root is out of reach, but they are a summary and not a substitute.

## Non-negotiables

- **Completion Law** - done = the verification command ran *this session* with its output in the
  report. Prior reports, READMEs, commit messages and comments are **claims**, not evidence.
- **Verification Duty** (Claude Code) - re-run Codex's verification yourself. Never advance a packet
  on Codex's word.
- **Repair-and-report is forbidden** - report the failure verbatim before proposing a fix.
- **Consume first** - search the Hardware Store before implementing any capability; log the search.
  Rebuilding a certified part without a documented reason is a defect.
- **No self-certification** - R&D's Verdict Gate is the only path into the Store.
- **One packet, one PR.** Never combine. Never fix things outside the packet; file them instead.
- **Non-destructive** - no deletes, resets, force-pushes, lockfile rewrites, migrations.
- **Founder merges. Always.** `main` is protected here with `enforce_admins` on, so this binds
  everyone including the founder.

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


## The doctrine set (canonical at the fleet root, one directory above this repo)

Read in this order. If any is unreadable, say so and stop; do not proceed on assumed context.

| # | file | what it governs |
|---|---|---|
| 1 | `../MATRYM_NORTH_STAR.md` | the mission and the Law: who we are |
| 2 | `../.ai/HANDOFF_PROTOCOL.md` | the exchange between Claude Code and Codex, the Verification Duty, extraction capture |
| 3 | `../.ai/GREEN_BUILD_DIRECTIVE.md` | the MODE: build, consolidate, integrate, test, get green, keep moving |
| 4 | `../.ai/ONE_FLEET_ONE_FLIGHT.md` | the FORMATION: one flight at a time, station-keeping, the six drift conditions |
| 5 | `../.ai/RELAUNCH_SEQUENCE.md` | the ordered flights. Flight 1 is Aethryn Green |
| 6 | `../.ai/CHIEF_ENGINEER.md` | register and duty: honest margins, the dissent duty, mentorship. Never permission |
| 7 | `../.ai/handoff.md` | the live board. **CURRENT FLIGHT is at the top.** Read at open, update at close |
| 8 | `../BUILD_STATE.md` | generated: the green line and the claims board. Never hand-edited |

**Precedence.** 1 and 2 are the Law. 3 and 4 are the mode and the formation, layered on top. 6 is
register only and overrides nothing. Where a lower number conflicts with a higher one, the LAW
wins: flag the conflict, do not resolve it yourself.

**Before editing any major file here:** read `../claims/CODEX.yaml` and
`../claims/CLAUDE_CODE.yaml`, and record your own claim in your own file. Neither agent edits the
other's. `make claims` at the fleet root refuses a board where two active claims from different
agents own overlapping ground.

**At session open, state it:** *"Current flight: X. My element: Y. This session serves it by: one
sentence. Station: claimed paths. Drift check: clear, or condition N."* If that sentence cannot be
said honestly, report the drift instead of starting work.
