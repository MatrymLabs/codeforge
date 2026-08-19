# AGENTS.md - codeforge

the flagship: a Python core with native lanes at different evidence stages and a self-auditing engineering stack.

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

## IN PLAIN TERMS, on every Bench Report

**Every Bench Report ends with this section. Both Benches. It is not optional and not filler.**

```
IN PLAIN TERMS
- What I actually did, in one or two sentences a non-specialist understands.
- Why it mattered for the Build, in one sentence.
- One thing worth knowing: the concept, pattern or tool this touched, named simply.
```

Rules that make it worth the three lines:

- **No jargon without a plain-word gloss.** "I added a mutation test (a test that deliberately
  breaks the code to prove the other tests would catch the break)."
- **Explain the WHY.** The diff already says what. The why is the part that teaches.
- **One concept per report, never a lecture.** Steady exposure beats a firehose.
- **Be honest in plain terms too.** "This works but I am not certain it is the best approach
  because X" is a valid and valuable plain-terms answer.
- **Do not explain the Principal Engineer's own doctrine, architecture or methodology back to
  him.** He is expert there. Teach the specific language, tool, algorithm or technique the task
  touched.

**This section is oversight as much as teaching.** If a Bench cannot say plainly what it did, the
work is confused or the Bench is unsure, and the vagueness is the signal. If the "why" does not
connect to the Build, the work may be drift that is correct only in isolation. The Principal
Engineer catches both from the explanation alone, without reading every line.

**"Teach me this"** is a standing command from the Principal Engineer about any report, decision,
file, diff, term or instrument. Stop and give a full plain-language walkthrough: what it is from
the ground up, why it exists and what breaks without it, how it works with a concrete example, how
it connects to what is being built, the one durable takeaway, and one direction to go deeper.
Assume intelligence, not prior knowledge. Reach for analogies from games, workshops, retro consoles
and engineering, which is the world he already knows. Teaching a decision means defending it.

Full doctrine: `.ai/TEACHING_LAYER.md` in the Workshop root.

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

## Prove safe before you destroy. MANDATORY, both Benches, until told otherwise.

**Standing doctrine, 2026-08-15. It governs every irreversible act, not only GitHub repositories.**

The ladder, and you take the highest rung that achieves the goal:

```
1. PULL DOWN     make a second copy first. A fetch costs seconds and cannot lose anything.
2. DISABLE       stop a thing running without removing it. Reversible in one command.
3. PRIVATE       remove it from view without removing it. Reversible.
4. ARCHIVE       make it read-only and inactive. Reversible.
5. DELETE        last, and only under the proof below.
```

**Proven-safe to delete means every commit, file or record exists somewhere else that is not the
thing being deleted, and you re-verified that IMMEDIATELY BEFORE the act rather than earlier in the
session.** State the count. "It should be fine" is not a proof and neither is a check from twenty
minutes ago.

**A Bench never performs step 5 without a per-item Principal Engineer stamp.** Not per batch. Per
item. A stamp for a list is a stamp nobody read.

**And check what the removal breaks before it breaks it.** On 2026-08-15 seven repositories went
private in one pass; two of them are cloned by CI. It survived only because that workflow already
used a deploy key. That was luck, and the check that would have made it knowledge costs one grep:

```bash
git grep -lniE "<the thing>" -- '.github/workflows/*' Makefile
```

**Removing a thing does not remove its claims.** Disabling two scanners left a README advertising a
security badge for a scan that no longer ran, which is a false claim in the one public repository.
When you disable, archive or delete something, grep for what still asserts it exists and fix the
claim in the same change or restore the thing.

**IN PLAIN TERMS applies here too.** An irreversible act reported without a plain-language sentence
saying what is now gone and where the copy lives is not reported.

## Blast radius: search the THING, not the spelling

**A blast-radius search that finds one spelling of a thing has measured one spelling, not the
thing.** Write this into every Build Sheet, and re-run it before trusting an allowlist.

On 2026-08-15 an order to move `content/seeds/` shipped with a blast radius of nine sites, found by  <!-- lexicon: allow -->
`git grep "content/seeds"`. A Bench started the move and immediately hit `tools/census.py`, which  <!-- lexicon: allow -->
was not in the allowlist because the path is never spelled that way there:

```python
SEED = Path(__file__).resolve().parent.parent / "content" / "seeds" / "aethryn"  # lexicon: allow
```

Re-searched properly, **nine source files and twenty test files** build that path from segments, and
`kernel/cast.py` defines a second copy of the constant. The order was wrong by an order of
magnitude, and the Bench refusing was the only reason it was caught before thirty files broke.

**The forms a search must cover, at minimum:**

| the thing | spellings to search |
|---|---|
| a path | the literal `a/b/c`, the segmented `"a" / "b"`, and any constant that resolves it |
| an identifier | the name, plus any string form in config, schema keys and CLI text |
| an environment variable | the read sites, which are few, not the set sites, which are many |
| a filename | the name, the stem, and any glob that would match it |

**The test of a blast radius is a command that returns nothing when the work is done.** If the
order cannot state such a command, the allowlist is a guess. WO-BP-2 states its own:
`git grep -lnE '"content"\s*/\s*"seeds"' -- '*.py' | grep -v ^tests/` must return nothing.  <!-- lexicon: allow -->

**And when a search finds thirty sites where you expected nine, that is usually not a bigger
chore. It is a finding.** Thirty places knowing one filesystem layout is duplication, and the right
order consolidates them onto one resolver rather than editing thirty.

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

## Bench toolchain

**This repository is polyglot and the non-Python toolchains are USERSPACE. A bare PATH has none of
them**, and `make check` inspects every language present, so a bench without them cannot run the
gate at all. Export this before anything else:

```bash
export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
```

**One export, and it must include `$PWD/.venv/bin`.** This section briefly carried a shorter one
without it, and a bench followed that line into exactly the failure this section exists to prevent:
`make check` reached the Go lanes, then died on `lint-imports: No such file or directory`, which
reads as a missing package and is a missing PATH entry. `lint-imports`, `ruff` and `mypy` are all
invoked by bare name from the Makefile, so the venv must be on PATH and not merely referenced by
`PY=`. Run this from the repository root, where `$PWD/.venv` resolves.

| tool | lives at | needed by |
|---|---|---|
| `ruff`, `mypy`, `pytest`, `bandit`, `lint-imports`, `detect-secrets-hook` | `$PWD/.venv/bin` | `lint-python`, `typecheck`, `test`, `imports`, `sast` |
| `go`, `gofmt` | `$HOME/.local/go/bin` | `lint-go`, `typecheck-native` |
| `golangci-lint`, `protoc-gen-go` | `$HOME/go/bin` | `lint-go`, `make proto` |
| `cargo`, `rustc` | `$HOME/.cargo/bin` | `lint-rust`, `typecheck-native` |
| `protoc`, `shellcheck`, `uv` | `$HOME/.local/bin` | `make proto`, `lint-shell`, `make env` |

**This table was MEASURED, not remembered.** Three earlier versions of this export were each
written from partial knowledge and each sent a bench into a different wall: the first omitted
`.venv/bin` and died at `lint-imports`, the second omitted `.cargo/bin` and died at `cargo: not
found`. The list above was produced by asking `command -v` for every bare-name tool the gate
invokes, and then running the whole gate under `env -i` with exactly this PATH and nothing else.
It exits 0. If you add a target that shells out to a new tool, add its row here and re-run that
test, because a doc that describes the author's shell is worth less than no doc at all.

**`make proto` before `make check`, on any bench that has not built here before.** `native/spine`
imports protobuf bindings that ADR-0012 git-ignores, so the Go build fails until they exist. CI
runs `make proto` as an explicit step for exactly this reason; a bench is no different.

Written down on 2026-08-14 after four dispatches died on it. `lint-go` and `proto` now name the
missing tool and print this export themselves, because the previous message reported a missing
toolchain as missing generated code and sent two agents to run `make proto`, which failed one
layer down on a tool that was also not there.

## The gate

```bash
cd /home/josh/Projects/MatrymLabs/codeforge
export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
make proto      # first run on a fresh bench; see "Bench toolchain" above
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
