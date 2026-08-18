# MATRYM LABS — MASTER CHECKLIST
## Where the whole enterprise stands. One page. Updated at each day close.
## `[x]` done with evidence · `[~]` partial · `[ ]` not started · `[?]` needs verifying

**The rule: a box is `[x]` only when a command proved it. Anything else is `[~]`
or `[?]`. This document is worthless the moment it flatters.**

Last updated: ____________  ·  Day: ______

---

## 1. FOUNDATION — the machine
```
[x] PC migrated from Pi, repos at C:\Projects\MatrymLabs
[x] rig specs recorded (i9-13900KF / 32GB / RTX 4090 / 2TB NVMe / Win11 Home)
[?] BIOS current on Z790-E (Raptor Lake microcode) + Intel Default power
[?] Defender exclusions, long paths, Developer Mode, sleep-off, OneDrive clear
[?] .gitattributes committed per repo, no committed .venv or abs-path symlinks
[?] git globals: autocrlf/fileMode/fsmonitor/untrackedcache/symlinks
[?] parallelism set: pytest -n auto, gradle workers.max 8
[ ] Tailscale on PC + Pi; NoMachine bound to it, no forwarded ports
[ ] Pi mirroring via scheduled git pull
[ ] winget DSC bootstrap file committed (machine reproducible from one command)
```

## 2. INSTRUMENTS — gates that actually catch things
```
[x] strict configs authored (ruff, mypy, pytest, clippy, golangci v2, detekt, etc.)
[~] configs merged to main — 4 of 9 landed day 229, rest need confirming  [?]
[ ] EVERY present language invoked by the gate (the dominant defect class)
[ ] EVERY gate calibrated red-then-green by the bench that did NOT write it
[x] security scanners on the merge path (caught a real Go stdlib panic)
[?] scanners invocable, not merely installed (trivy/gitleaks/govulncheck on a fixture)
[x] ledgers exist with day-zero counts + reproduce commands
        noqa 733 · mypy 181 across 64 modules · Kotlin 16
[ ] UNMEASURABLE reported as a first-class verdict across all gates
[ ] differential test executable on all 4 Blueprints (2 currently cannot run)
```

## 3. DOCTRINE — installed and honest
```
[?] docs/WORKSHOP.md saved verbatim in the tree
[?] docs/ROAD_TO_THE_FACTORY.md saved verbatim in the tree
[?] CLAUDE.md file map: every path resolves (verified, not assumed)
[?] HARD LAW blocks present VERBATIM (pbkdf2/plaintext, never-lowercase-secrets,
        CMMC/POA&M/NARA)
[?] board header: active launch, anchors, Active Build, standing gates
[x] anchor system live — 42 orders sorted, 5 PARKED, 3 killed with reasons
[x] two commands defined (open project, rack and stack)
[ ] historical session logs moved out of the live board
```

## 4. THE FACTORY STAGES — the actual scoreboard
```
[~] STAGE 0  Baseline held — confirmed fresh each morning, 10 boxes
[ ] STAGE 1  Crank turns once: one Blueprint -> one working output
       [ ] DONE-1  Blueprint: produce · persist · emit · restart · survives
       [ ] DONE-2  RF-001: load · decode · manifest · display · bytes untouched
[ ] STAGE 2  Generality proof: a second, non-game product (Excel-to-PDF)
       [ ] built through the same loop
       [ ] used once by someone who is not the founder
[ ] STAGE 3  Intake real: a third product started from an Intake Form
[ ] STAGE 4  Language ladder: one PROVEN lane per rung
[ ] STAGE 5  Factory floor: one work order dispatched from inside the world
```

## 5. LANGUAGE LANES — CANDIDATE / INSTALLED / GATED / PROVEN
```
python        [~] GATED    -> PROVEN when DONE-1 ships          calibrated: ______
rust          [?] INSTALLED, gate needs calibration             calibrated: ______
go            [?] INSTALLED, gate needs calibration             calibrated: ______
shell         [?] GATED (4 rules, noisy 5th documented out)     calibrated: ______
kotlin-jvm    [~] GATED (detekt baseline 16) -> PROVEN on RF-001 calibrated: ______
gdscript      [ ] INSTALLED, real gate is typed GDScript + headless compile
typescript    [ ] CANDIDATE — deferred to the SaaS rung
csharp        [ ] CANDIDATE — deferred
cpp / sql / terraform / powershell  [ ] CANDIDATE
```
*A lane is not supported because it is listed. Listing is not support.*

## 6. HARDWARE STORE
```
[x] structure real, two tiers (working shelf ~104 / certified ~8)
[ ] Parts harvested from a real delivered product (zero so far)
[ ] any Part with two genuine consumers and both proofs passing
[ ] lane records exist for every GATED lane
[ ] first Part extracted from the two dones (verify-then-commit is the candidate)
```

## 7. PRODUCTS DELIVERED
```
[ ] 1st Target Product delivered and running
[ ] 2nd Target Product, different in kind
[ ] any product a person other than the founder has run
```
**Current count: 0. This is the number that matters most.**

## 8. OUTSIDE THE WORKSHOP
```
[ ] one artifact saved and shown to one human outside Matrym Labs
[ ] one person has used something the factory built
[ ] one public repo a stranger could read without embarrassment
```
Days since external contact: ______
*Every other metric here is self-referential. This section is the only one that isn't.*

## 9. STANDING DISCIPLINES — are they actually running?
```
[ ] Codex queue never below 3 (idle bench = logged defect)
[ ] every order carries an anchor (no anchor = undispatchable)
[ ] every return independently re-verified by the other bench
[ ] full checks after every leg, no bypass flags
[ ] IN PLAIN TERMS on every bench report
[ ] reverse-engineer pass, tiered, on completed work
[ ] two stamp windows, not per-item approval
[ ] ledger counts stated at day close, trending down
[ ] zero new doctrine files while dones are unproven
```

---

## THE FOUR NUMBERS (say them out loud at every day close)
```
Products delivered:            ____
External users:                ____
Days since external contact:   ____
Ledger totals (noqa/mypy/kt):  ____ / ____ / ____
```

## THE ONE QUESTION
**What did the Workshop produce today that a stranger could use?**

If the answer is "nothing" more than two days running, the machine is building
itself again. Stop and turn the crank.
