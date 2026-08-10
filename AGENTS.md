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
