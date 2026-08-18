# THE UNIVERSAL CLAUSE

**Everything in this document applies to all of Matrym Labs.**

Every repository. Every Blueprint. Every Target Product. Every language lane. Every
tool. Every bench. Every session. Every work order. Every line of code produced by
Codex, by Claude Code, or by the Principal Engineer himself.

CodeForge, Aethryn, RetroForge, the Hardware Store, a one-file script, a spike, a
prototype, a demo, a favor, a five-minute fix — the same standard governs all of it.
The Workshop has one methodology. It does not fork per project.

**No exemption is granted for:**
- size — a ten-line script obeys the same law as the engine
- novelty — a new project inherits the standard automatically and does not opt in
- urgency — "we needed it fast" is not a proof run
- authorship — work written by the founder is verified exactly like work written by a bench
- familiarity — a repeat finding is not a smaller finding
- language — a lane that is new to the Workshop is not a lane that is exempt from it
- product type — a game, a converter, a plugin, and a service are held identically

**The only legitimate variation is applicability, and applicability is resolved, never
assumed.** A control that does not apply is marked `NOT_APPLICABLE` with a recorded
reason. It is never silently skipped. "This didn't seem relevant" is not a resolution;
it is an unmeasured claim, and unmeasured claims are the defect class this Workshop
exists to eliminate.

**The one bounded exception is the R&D Tech Lab.** Uncertain ideas, unfamiliar
languages, outside references, and experiments may run there without full proof —
that is the Lab's purpose. But nothing leaves the Lab. An experiment becomes a
capability only by entering the factory at INTAKE and earning its way through the
standard like anything else. Work that graduates from the Lab carries no credit for
having worked there.

**This clause binds the Principal Engineer.** The founder may change the standard —
deliberately, in writing, with a dated reason — but he may not step around it. A rule
the owner exempts himself from is not a rule; it is a preference, and the benches will
learn to read it as one.

**It binds anyone who joins later.** Any future person, agent, contractor, or tool
inherits this clause on arrival. It is not onboarding material to be absorbed
gradually. It is the condition of touching the tree.

---

One Workshop. One methodology. One standard, applied everywhere, to everyone,
including the person who wrote it.

Execute. Prove. Capture. Reverse engineer. Harvest. Optimize. Continue.

---

# WORKSHOP.md — THE ONE OPERATING DOCUMENT
## Matrym Labs. Install once, then this governs every session.
## Companion files: ROAD_TO_THE_FACTORY.md (the vision) and CLAUDE.md (the card).
## Nothing else is required reading.

---

# PART 1 — INSTALL (once, tonight, ~20 minutes)

**[FOUNDER]**
1. `cd C:\Projects\MatrymLabs\codeforge` then `mkdir docs -Force`
2. Save THIS file as `docs\WORKSHOP.md`. Save your Road doc as
   `docs\ROAD_TO_THE_FACTORY.md`. Save the two research reports as
   `docs\reference\windows-baseline.md` and `docs\reference\toolkit-optimization.md`.
3. Hand this file to Claude Code and say: "Run Part 1 [CC] steps."

**[CC]**
4. Rewrite CLAUDE.md's FILE MAP so it names only paths that resolve. Test each one.
   Add these two lines to its COMMANDS section:
   - `"rack and stack the bench"` -> Part 2 of docs/WORKSHOP.md. Execute, don't discuss.
   - `"open project <X>"` -> Part 2 of docs/WORKSHOP.md. Resolve, scope, rack and stack.
   Point the law pointer at a real, non-trivial document. Confirm the three HARD LAW
   blocks (pbkdf2/plaintext, never-lowercase-secrets, CMMC/POA&M/NARA) are present
   VERBATIM. Restore from the old card if missing. Never paraphrase them.
5. Put these four lines at the very top of `.ai/WORKBENCH.md`:
```
Active launch: docs/WORKSHOP.md Part 4
Anchors: DONE-1 | DONE-2 | L3 | QUARRY
Active Build: M2 Engine Real (CodeForge). RF-001 rides as DONE-2.
Standing gates: docs/WORKSHOP.md Part 3
```
6. Move historical session logs out of the live board into `.ai/history/`.
7. Verify and paste: every CLAUDE.md path resolves, board header correct, HARD LAW
   present, suite still green, git clean and pushed, nothing stranded.
   One commit per logical change.

---

# PART 2 — THE COMMANDS

## "open project <X>"
1. Read the board. Resolve X to its anchor. State: "Project open: X. Anchor: Y."
2. If X maps to no anchor on the board: say so and stop. Either the founder is
   changing the launch (his call) or the work belongs in PARKED. Never stretch a
   label to fit.
3. Scope: every order authored from now carries that anchor and a PROJECT line.
   Receiving-bench verification is NEVER scoped out.
4. Run rack and stack against X.
5. On "close project" or day close: one line of state to `.ai/handoff.md` under X,
   so the next open resumes instead of restarts.
6. Mid-day switches are reported: "closed A at <state>, opened B."

## "rack and stack the bench"
1. **Orient** — read the board and the active launch. State in one line: what the
   Build is, what done looks like, what stands between.
2. **Ground-truth (15 min cap)** — worktree guard, board state, queue depth,
   re-verify one "done" claim. Name the three things actually blocking the Build.
3. **Rack** — identify the critical-path legs. Not adjacent nice-to-haves; the legs
   the Build cannot close without. Split: implementation (Codex) vs
   architecture/verification (Claude Code).
4. **Stack** — order by dependency, the leg that unblocks the most goes first.
   Batch-author 3-5 Codex orders. Queue floor is three, always.
5. **Load and go** — dispatch, report the loadout in one block, start the first leg.
   Do not ask permission between steps.

---

# PART 3 — STANDING LAW (every session, no exceptions)

## Posture
Reversible work executes on sight. Git is the safety net. **Run until blocked:**
finishing a leg is a commit and the next leg, not a stop.
STOP only for: unrecoverable deletion, force-push/history rewrite, data loss,
destructive migration, secret exposure, another bench's uncommitted tree, publishing,
merging to main, spending money — or a genuine fork, a failed precondition, a red
gate, a missing credential.

## Verification (never cut — this is why fast is safe)
- Done = the verify command ran THIS session, output captured. SKIPPED is not PASS.
- Measured state expires. Reproduce; never quote an old report.
- Observe failure before repair.
- The bench that builds an instrument NEVER certifies it. Calibration is always the
  other bench.
- A gate that cannot execute reports **UNMEASURABLE**. A crash is not a test result.
- The founder merges. Only the founder.

## Every work order carries, or it is undispatchable
Anchor · Goal · Invariant · Scope · Non-goals · Repository · File allowlist ·
Bench claim · Language (one only) · Tools · Hardware Store search · Contract tests ·
Expected Break Test · Definition of done · Proof Run command · Rollback ·
Approval gates · Size (S/M) · Reusable Part signals

An order missing an anchor, allowlist, or proof is refused back. That is a valid return.

## Anchors
The anchor set lives on the board and changes only when the launch changes. New
launch -> re-derive the set, post it, re-anchor the queue in one pass. Work serving no
anchor goes to `.ai/PARKED.md` with one wake-line. Never expand an anchor's meaning to
make work fit. If parked work keeps demanding attention, that is a signal for the
FOUNDER to consider changing the launch.

## Holding the baseline
- Full checks after every leg. No bypass flags. They are cheap on this rig.
- No new noqa/allow/ignore without a reason comment.
- Burn-down by side effect: a file touched for work loses its baselined violations too.
- Ledger counts stated at day close, trending down, never up.
- A gate that greens suspiciously fast gets re-calibrated, not trusted.

## Reverse engineer and harvest (tiered)
One line on routine orders. Full pass on new language lanes, second-occurrence
patterns, and anything surprising. Record: what invariant it protects · failure
observed before repair · tools invoked and lanes touched · Store search and result ·
patterns appearing twice (Part candidate on the pull rule) · product-specific vs
Workshop-wide · anti-patterns and Cases · lane status if proven.
Reusable Part signals are never blank — write "none observed" if nothing.

## Founder rhythm
Two stamp windows: midday and close. Verdicts queue between them.
Pre-authorized, auto-proceed: content-lane units, Class 1 prose, test/reproduction
writing, config-layer baseline items.
Wait for a stamp: merges, contract/schema/wire changes, deletions, money.

## Teaching layer
Every bench report ends with **IN PLAIN TERMS**: what I did in plain words, why it
mattered, one concept worth knowing. "Teach me this" = stop and teach fully.
Vagueness there is itself a flag.

## Handoff format
```
=== READY FOR CODEX (batch of N) ===
ORDER 1: <id> · anchor · language · allowlist · verify command
[full self-contained orders below]
=== END BATCH ===
```
```
=== RETURN TO CLAUDE CODE (batch of N) ===
ORDER 1: <id> · DONE/BLOCKED · verify output · extraction signal
=== END RETURN ===
IN PLAIN TERMS: <for the founder>
```

## Rig rules
Heavy builds sequenced, never stacked (32GB): gradle workers.max 8, cargo cap 16 only
if swapping, pytest -n auto. 4090 is for Godot and optional local models — it does
nothing for builds. Sleep stays off (NoMachine). Pi mirrors via scheduled git pull.


## MERGE AUTHORITY (delegated)

Claude Code merges routine work without a stamp. The gates are the check; the
founder reviews the digest, not each merge.

**AUTO-MERGE when ALL of these are true:**
- every required status check is green, no bypass flags, no skipped gate
- the change carries one anchor and touches one language
- the other bench independently re-ran the proof and it passed
- no contract, schema, wire-protocol, public API, or CLI surface changed
- no dependency added, removed, or version-bumped
- no file deleted that the same change did not create
- no new suppression (noqa/allow/ignore) without a reason comment
- single repository
- diff under 400 changed lines

Merge it, log it, keep building. Do not ask.

**STAMP REQUIRED — stop and queue for the founder:**
- contract, schema, wire-protocol, public API, or CLI surface change
- competing candidates or any fork with two viable directions
- deletion of pre-existing files, or history rewrite of any kind
- new, removed, or bumped dependency
- anything touching authentication, secrets, or permissions
- cross-repository change
- a gate that reddened and was then made green by changing the gate
- diff over 400 lines
- anything the agent is uncertain about — uncertainty itself is the trigger

**NEVER automated, regardless of gates:**
- publishing, releasing, or tagging a version (a merge is revertible; a published
  artifact is not)
- force-push, history rewrite, branch deletion
- anything spending money
- deleting a remote repository or its issues

**Required safeguards, all three:**
1. Branch protection on main: PR required (0 approvals), all status checks
   required, linear history, no force-push, no deletions. The ruleset is what
   makes delegation safe — configure it before merging anything automatically.
2. `.ai/MERGE_LOG.md`: one line per auto-merge — date, PR, anchor, one-line
   summary, the checks that passed. Presented at the close stamp window as the
   day's merge digest. The founder sees everything, just not one at a time.
3. Any auto-merge that later causes a defect is recorded as a Case, and its
   criteria tighten. The list above is a floor that ratchets up, never down.

**The rule underneath:** automate the merges that require no judgment, keep the
founder for the merges that are entirely judgment. If an agent has to weigh two
reasonable options, that is a stamp, not a merge.

---

# PART 4 — THE ACTIVE PLAN

## Phase 0 — BASELINE HELD (0800, 30-min cap, evidence per box)
Yesterday's report is a claim until re-measured this morning.
```
[ ] merged configs are on origin/main, not a branch
[ ] shell config carries its documented-out rule note
[ ] killed orders closed with reasons; PARKED populated; queue 100% anchored
[ ] the CX-BP-9 vs c6364a15 fork is RULED, one merged, other closed
[ ] no stranded commits or reports off the push path (fresh gate run)
[ ] full suite green on main, every repo, run fresh NOW
[ ] calibration spot-check, three rotating lanes: plant -> red, remove -> green
[ ] ledgers at or below day-zero: 733 noqa / 181 mypy / 16 Kotlin
[ ] scanners INVOCABLE: trivy, gitleaks, govulncheck each return findings on a fixture
[ ] suite runner resolves the PROJECT interpreter, collected count > 5,000
```
Ten green -> declare **BASELINE HELD**. Any red -> that box is the day's first work.

## Phase 1 — THE CRANK TURNS ONCE
**DONE-1 (M2 Engine Real):** Blueprint produced · persists · Target Product emitted ·
restart, state survives · full transcript captured.
*Blocker on the path: the flagship Blueprint's missing overlay makes the differential
UNMEASURABLE. That is a DONE-1 blocker, not instrument work. Fix it first; the
differential goes honest on all four Blueprints as a side effect.*

**DONE-2 (RF-001):** synthetic ROM loads · metadata and tiles decode · traceable
manifest emitted · displays through Rider · ROM bytes unmodified (hash before/after).

Codex: 3-5 disjoint orders, one language each, run until blocked, one RETURN block.
Claude Code: drive the DONE-1 pipeline, verify every return independently, queue at 3+.

## Phase 2 — REVERSE ENGINEER both dones (full pass — first real use, ideal material)

## Phase 3 — EXTRACT THE APPARATUS (last act, not first)
Draft only three, derived strictly from what the two dones actually required:
Intake Form v1 (ten fields — test: could BOTH dones have been requested with these
alone?) · Blueprint v1 (fields the dones actually used, nothing speculative) ·
Language Lane records for lanes those dones PROVED, with calibration dates.
Everything else stays PARKED until a third product gives it a second consumer.
*A schema built before the build that consumes it violates the pull rule.*

## Phase 4 — DAY CLOSE
Shipped with evidence · reds verbatim · ledger delta · queue at 3+ · Pi mirror
current · IN PLAIN TERMS · days since external contact said out loud · zero new
doctrine files · one artifact saved to show a human outside the Workshop.

---

# PART 5 — THE MORNING, THREE PASTES

```
1. Open Claude Code. Do NOT open a project yet.
2. "Run Phase 0 of docs/WORKSHOP.md. Ten boxes, evidence each, 30-min cap.
    Report BASELINE HELD or the reds."
3. On BASELINE HELD:  "open project CodeForge"
4. Then:              "rack and stack the bench"
5. Carry the READY FOR CODEX block to Codex.
6. Carry the RETURN block back. Repeat. Stamp at midday and close.
```

---

**Hold baseline. Turn the crank. Study the output. Harvest the Parts. Continue.**
