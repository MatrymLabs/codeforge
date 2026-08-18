# MATRYM LABS — MASTER CHECKLIST
## Where the whole enterprise stands. One page. Updated at each day close.
## `[x]` done with evidence · `[~]` partial · `[ ]` not started · `[?]` needs verifying

**The rule: a box is `[x]` only when a command proved it. Anything else is `[~]`
or `[?]`. This document is worthless the moment it flatters.**

Last updated: 2026-08-18  ·  Day: 230
Filled by: Claude Code (sections 2,3,4,6,7,8,9 + lane judgment), merged with Codex's
report (section 1, the scanner-fixture box, the lane toolchain half). Claude Code is the
only bench that writes this file; Codex reports and does not edit it.

---

## 1. FOUNDATION — the machine
```
[x] PC migrated from Pi, repos at C:\Projects\MatrymLabs
[x] rig specs recorded (i9-13900KF / 32GB / RTX 4090 / 2TB NVMe / Win11 Home)
[ ] BIOS NOT CURRENT on Z790-E — version 0816, released 2023-02-22, 1273 DAYS OLD
        It predates every Intel Raptor Lake microcode fix for the Vmin Shift instability
        (0x125 May 2024, 0x129 Aug 2024, 0x12B Sep 2024). The i9-13900KF is the part those
        fixes exist for. This is a hardware-degradation risk, not a checkbox.
    [?] Intel Default power limits — not exposed by ASUS/Windows WMI; needs a BIOS-screen read
[~] Defender / paths / Developer Mode / sleep / OneDrive
        DEFENDER IS NOT THE ACTIVE SCANNER. WinDefend is Stopped/Manual because AVIRA SECURITY
        is the registered antivirus (SecurityCenter2 lists it, state 0x41000). Codex read the
        Get-MpPreference failure as "unavailable"; the real answer is "superseded". The
        exclusions question therefore belongs to Avira, not Defender, and is unanswered.
    [x] long paths enabled (LongPathsEnabled=1)
    [ ] Developer Mode NOT enabled (AllowDevelopmentWithoutDevLicense absent)
    [x] sleep never (High performance, AC and DC standby idle = 0)
    [x] OneDrive does not scope the repos (the OneDrive Projects path does not exist)
[x] .gitattributes committed in all 7 registered repos; no committed .venv anywhere;
        no absolute-path symlinks (no 120000 entries in any index)
[x] git globals recorded: autocrlf=false, filemode=false, fsmonitor=true,
        untrackedCache=true, symlinks=true
[x] parallelism set: JOBS ?= auto driving pytest -n; gradle parallel=true, workers.max=8
[ ] Tailscale on PC + Pi; NoMachine bound to it, no forwarded ports
        PC Tailscale is INSTALLED BUT LOGGED OUT (BackendState NeedsLogin, no IPs, Online false)
        NoMachine listens on 0.0.0.0:4000 AND [::]:4000 — all interfaces, NOT Tailscale-bound.
        No Windows portproxy entries exist, so nothing is forwarded, but the listener is open on
        every interface the machine has. That is the finding, and it is a security one.
    [?] Pi side unverified: SSH to skynet fails on host key verification (TCP 22 reachable)
[?] Pi mirroring via scheduled git pull — UNVERIFIED, same SSH host-key failure.
        Last run time unknown. Resolve: accept the host key, then
        ssh skynet "systemctl list-timers --all; crontab -l" 
[x] winget DSC bootstrap committed — machine-bootstrap/.winget/configuration.dsc.yaml,
        blob 9582f60a, present in both the founder root and ship-claude
```

## 2. INSTRUMENTS — gates that actually catch things
```
[x] strict configs authored (ruff, mypy, pytest, clippy, golangci v2, detekt, etc.)
[x] configs merged to main — ALL 9 now on origin/main (was 4 of 9 on day 229)
        deny · trivy · rustfmt · .shellcheckrc · .gitleaks · .golangci · mutants · pyproject · detekt
[~] EVERY present language invoked by the gate — 6 of 7 in `make lint`
        code present: py 883 · kt 8 · tf 8 · sh 6 · go 4 · rs 1 · c 1
        `lint` wires: python rust go shell terraform c.  KOTLIN IS NOT IN IT (standalone by
        a recorded 2026-08-14 decision; CI's `jvm` job runs ktlintCheck, so it is governed)
    [ ] DETEKT IS CONFIGURED AND INVOKED NOWHERE. detekt.yml is on main with a 16-entry
        baseline; 0 occurrences in ci.yml, and `make lint-kotlin` runs ktlintCheck only.
        A gate that exists and is never run is the defect class this line names.
[~] EVERY gate calibrated red-then-green — harness has 13 cases, 3 re-run 2026-08-18
        covered: ruff(3) mypy(2) pytest bandit gitleaks c go rust shellcheck terraform
        NO CASE EXISTS for: detekt/kotlin, trivy, cargo-deny
[x] security scanners on the merge path (caught a real Go stdlib panic)
[x] scanners invocable AND PROVEN ON A PLANTED HIT (Codex 2026-08-18, fixtures removed)
        gitleaks  generic-api-key on a fake token — NOTE: the FIRST fixture found nothing.
                  A weak plant proves nothing; the box passed only after a realistic one
        trivy     AWS-0107 HIGH, unrestricted ingress 0.0.0.0/0 in a terraform fixture.
                  Also learned: this trivy build has no --scanners flag; the working form is
                  trivy config --misconfig-scanners
        govulncheck  GO-2026-5023 and GO-2022-0968 in x/crypto/ssh, reachability-aware
[x] ledgers exist with day-zero counts + reproduce commands
        DAY ZERO 2026-08-18 on main 198c81f0: noqa 734 · mypy 181 across 64 modules ·
        detekt 16 · Gradle CC 0.  The 2026-08-17 figures are superseded: they were taken
        against an unmerged branch that landed the same evening
[ ] UNMEASURABLE reported as a first-class verdict across all gates
[ ] differential test executable on all 4 Blueprints — CONFIRMED BROKEN 2026-08-17
        run_differential('aethryn') raises FileNotFoundError on a missing world_overlay.json;
        aethryn and spiral-ascent have none, first-forge and seam-probe do. It raises rather
        than reporting, so it has read as a broken environment rather than a broken gate
```

## 3. DOCTRINE — installed and honest
```
[x] docs/WORKSHOP.md saved verbatim — 211 lines, sha256 identical to source
[x] docs/ROAD_TO_THE_FACTORY.md saved verbatim — 598 lines, sha256 identical
[x] CLAUDE.md file map — 14 of 14 paths tested individually from the Workshop root.
        4 dead paths removed; the law pointer aimed at a 9-line retired stub and now
        points at MATRYM_WORKSHOP_CANON.md (1,527 lines)
[x] HARD LAW blocks present VERBATIM — all 5 extracted blocks byte-identical to the
        pre-v2 card. They were ENTIRELY ABSENT (0 hits for all six terms), dropped when
        the card was shortened in #336. Restored by extraction, never retyped
[x] board header — 4 lines at the top of .ai/WORKBENCH.md, one deviation recorded in-file
        (`Active Build:` bolded; unbolded it failed active_build_gate.py)
[x] anchor system live — 42 orders sorted, 5 PARKED, 3 killed with reasons
[x] two commands defined (open project, rack and stack)
[x] historical session logs moved — 1,552 lines to .ai/history/, board 2,736 -> 1,200.
        Accounting proved: exactly 1 line of main is in neither file, the retired ANCHOR: L0
```

## 4. THE FACTORY STAGES — the actual scoreboard
```
[x] STAGE 0  Baseline held — BASELINE HELD declared 2026-08-18, 10 of 10 boxes
[ ] STAGE 1  Crank turns once: one Blueprint -> one working output
       [ ] DONE-1  Blueprint: produce · persist · emit · restart · survives
                   BLOCKED FIRST: the flagship Blueprint has no world_overlay.json, so the
                   differential is UNMEASURABLE on it. Part 4 names this as a DONE-1 blocker
       [ ] DONE-2  RF-001: load · decode · manifest · display · bytes untouched
                   NO ORDERS, NO BENCH ASSIGNED, NOTHING WRITTEN. Half the launch has no
                   work behind it. This is the largest hole on the board
[ ] STAGE 2  Generality proof: a second, non-game product (Excel-to-PDF)
       [ ] built through the same loop
       [ ] used once by someone who is not the founder
[ ] STAGE 3  Intake real: a third product started from an Intake Form
[ ] STAGE 4  Language ladder: one PROVEN lane per rung
[ ] STAGE 5  Factory floor: one work order dispatched from inside the world
```

## 5. LANGUAGE LANES — CANDIDATE / INSTALLED / GATED / PROVEN
```
python        [~] GATED    -> PROVEN when DONE-1 ships          calibrated: 2026-08-18
rust          [~] GATED (clippy -D warnings; case exists)       calibrated: case, not re-run
go            [~] GATED (golangci v2 + govulncheck source)      calibrated: 2026-08-18
shell         [~] GATED (4 rules, noisy 5th documented out)     calibrated: case, not re-run
kotlin-jvm    [ ] NOT GATED: detekt is configured and RUN NOWHERE; ktlint only  calib: none
gdscript      [ ] CANDIDATE — 0 .gd files tracked. Toolchain installed ahead of its code
typescript    [ ] CANDIDATE — 0 .ts/.tsx tracked, deferred to the SaaS rung
csharp        [ ] CANDIDATE — 0 .cs tracked, deferred
cpp / sql / powershell             [ ] CANDIDATE — 0 files tracked for each
terraform     [~] GATED (terraform v1.15.8, fmt -check in lint) calibrated: case exists
c             [~] GATED (gcc 16.1.0 / clang 22.1.8; cc absent, Makefile falls back correctly)
lua           [ ] NO CODE AND A CI JOB. 0 .lua files tracked, yet ci.yml has a `lua` job.
                  The inverse of an ungoverned language: a gate guarding nothing.

TOOLCHAIN VERSIONS (Codex, 2026-08-18): python 3.13.12 · ruff 0.16.2 · mypy 2.3.0 ·
pytest 9.1.1 · rustc/cargo 1.97.1 · clippy 0.1.97 · go 1.26.5 · golangci-lint 2.12.2 ·
govulncheck v1.7.0 · shellcheck 0.11.0 · java 24.0.2 Temurin · terraform 1.15.8 ·
gcc 16.1.0 · clang 22.1.8.  gradle/ktlint/detekt report ABSENT as bare tools, which is
expected: the Kotlin lane runs through ./gradlew, not a system install.

GO VERSION DIVERGENCE, unresolved: bench 1.26.5 · CI pins 1.25 · go.mod says 1.24. Three
numbers. The bench compiles and scans with a toolchain CI does not use, which is the exact
class the parity guard was built for and does not yet cover. (1.26.5 is safe for
GO-2026-4971, which was reintroduced in 1.26.0 and fixed in 1.26.3.)
```
*A lane is not supported because it is listed. Listing is not support.*

## 6. HARDWARE STORE
```
[x] structure real, two tiers — certified 22 entries, working shelf 104 parts (measured)
[ ] Parts harvested from a real delivered product (zero so far)
[ ] any Part with two genuine consumers — 13 of 104 name ANY consumer; none has two
        with both proofs passing
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
Days since external contact: UNKNOWN — never recorded. The first honest act here is to
start the counter, not to guess it.
*Every other metric here is self-referential. This section is the only one that isn't.*

## 9. STANDING DISCIPLINES — are they actually running?
```
[~] Codex queue never below 3 — held 3-5 through 2026-08-17, EMPTY right now
[x] every order carries an anchor — 0 rows still labelled L0; packets gate READY 2/2
[x] every return independently re-verified — every Codex return on 2026-08-17 was re-run,
        and 3 of the day's claims did not survive it
[x] full checks after every leg, no bypass flags — no gate was skipped or weakened; the one
        gate scope change (evidence_gate) shipped with a test proving it still fires
[x] IN PLAIN TERMS on every bench report — present on every report this session
[ ] reverse-engineer pass, tiered, on completed work — NOT RUN. Zero passes so far
[ ] two stamp windows, not per-item approval — still per-item in practice
[~] ledger counts stated at day close, trending down — stated; day zero is today, so
        nothing can yet be said about direction
[x] zero new doctrine files while dones are unproven — LEDGER/PARKED/handoff are registers,
        and the anchor system went on the board rather than into a new doctrine file
```

---

## THE FOUR NUMBERS (say them out loud at every day close)
```
Products delivered:            0
External users:                0
Days since external contact:   UNKNOWN (never counted; the counter starts today)
Ledger totals (noqa/mypy/kt):  734 / 181-in-64 / 16
```

## THE ONE QUESTION
**What did the Workshop produce today that a stranger could use?**

**2026-08-18: nothing.** Two days running, counting 2026-08-17, which produced no product either.
By this document's own rule that is the stop condition. Everything built on both days was
instruments, doctrine and the machine that builds the machine. The instruments are genuinely
better and caught genuinely real defects; none of that is a product a stranger could use.

If the answer is "nothing" more than two days running, the machine is building
itself again. Stop and turn the crank.

---

## REMAINING `[?]`, each with the command that resolves it

```
Intel Default power limits      read it off the BIOS screen; no WMI class exposes it
Avira exclusions                the AV is Avira, not Defender. Its exclusion list has never
                                been read, and a scanner watching C:\Projects is a build-speed
                                and file-lock question as much as a security one
Pi Tailscale state              ssh skynet "tailscale status --json"   (blocked: host key)
Pi NoMachine binding            ssh skynet "ss -ltnp | grep 4000"      (blocked: host key)
Pi mirror schedule + last run   ssh skynet "systemctl list-timers --all; crontab -l"
                                ALL THREE need the host key accepted first, once, by hand.
                                That is a founder action: accepting a host key is a trust
                                decision and not an agent's to make.
```

## FINDINGS THIS AUDIT PRODUCED, ranked by what they cost if ignored

```
1. BIOS 0816 is 1273 days old on an i9-13900KF, predating every Raptor Lake microcode fix
   for the Vmin Shift degradation. Silicon damage is cumulative and not reversible by a
   later update. This is the only finding on the page that gets worse while nobody looks.
2. NoMachine listens on 0.0.0.0:4000 while Tailscale is LOGGED OUT. Remote access is open
   on every interface and the private network that was supposed to carry it is off.
3. detekt is configured, has a 16-entry burn-down ledger, and is invoked by nothing.
4. DONE-2 (RF-001) has no orders, no bench, and nothing written. Half the launch.
5. Go: bench 1.26.5, CI 1.25, go.mod 1.24. Three numbers where there should be one.
6. A `lua` CI job guards zero .lua files.
```

---

## 10. TOOL UTILIZATION REGISTRY
*Road v3 §11: a tool is not integrated because it is installed. It counts only when
invoked through a captured proof command. Same ladder as language lanes.*

**Status per tool: `LISTED` → `INSTALLED` → `INVOCABLE` (proof command captured) →
`REGISTERED` (a record exists with proof + inputs/outputs + lanes)**

```
[ ] Tool Utilization Registry file exists at all           <- currently missing entirely
[ ] every tool a Blueprint depends on has a record
[ ] every record carries: tool_id, executable, version_command, proof_command,
    supported_inputs, supported_outputs, language_lanes, known_faults

BUILD + PROVE TOOLS (in use now)
Rider          [?] INSTALLED   no proof command: nothing in the tree invokes Rider headlessly
uv/python      [x] INVOCABLE   make check (python 3.13.12, ruff 0.16.2, mypy 2.3.0, pytest 9.1.1)
cargo          [x] INVOCABLE   make lint-rust -> cargo fmt --check && clippy -D warnings (1.97.1)
go             [x] INVOCABLE   make lint-go / security-go (bench go 1.26.5; CI pins 1.25)
gradle         [x] INVOCABLE   ./gradlew ktlintCheck  (wrapper, not a system install)
node/npm       [ ] NOT PRESENT in this repo; no package.json, no JS/TS lane here
git/gh         [x] INVOCABLE   used continuously; gh authenticated as MatrymLabs
task/make      [x] INVOCABLE   make is the control panel; Task 3.52.0 installed and UNUSED here
trivy/gitleaks/govulncheck  [x] INVOCABLE, PROVEN ON A PLANTED HIT (see section 2)

REGISTERED count is still ZERO. Every [x] above is INVOCABLE, one rung below REGISTERED,
because no registry file exists to hold a record. Invocable is not registered, exactly as
installed is not invocable. The rung is the point of the ladder.

RETROFORGE TOOLS (none required for DONE-2)
Aseprite       [ ] DEFER — Stage 4, asset pipeline rung
Tiled / LDtk   [ ] DEFER — map rung
FCEUX/Mesen    [ ] DEFER — emulator integration, not in the read-only slice
cc65/ca65/Asar [ ] DEFER — assembly/patch rung
FLIPS/xdelta   [ ] DEFER — patch rung
Ghidra/radare2 [ ] DEFER — reverse-engineering rung, wrap not build
Godot          [ ] DEFER — Engine-2D rung
```
*Nothing above moves off DEFER without an intake that needs it.*

---

## 11. RETROFORGE — CodeForge capability status
*RetroForge is a CodeForge module. The Rider plugin is one projection of it, not
the thing itself.*

### Platform ladder (same ladder as language lanes)
```
NES     [~] target of DONE-2 — core BUILT and TESTED, slice not yet proven end to end
            kernel/retroforge: artifact, binary, codec, manifest, platforms/planar_2bpp
            40 Python tests pass; Kotlin side has NesRom, AsciiTileProjection,
            ManifestWriter, Seam with 4 test files. Fixtures are SYNTHETIC and built in
            the tests (b"NES\x1a" headers, hand-made CHR), so the legal block holds:
            no ROM is committed anywhere.                       proven: NOT YET
SNES    [ ] DEFER — architecture may be discussed, not implemented
Genesis [ ] DEFER — architecture may be discussed, not implemented
GB / GBC / GBA / SMS / PCE / N64   [ ] DEFER — future only
```

### Rider integration ladder
```
L1  external tools / run configs invoking retroforge commands   [ ] nothing invokes it
L2  CodeForge tool records for what L1 invokes                  [ ] no registry exists
L3  RetroForge core                                             [x] BUILT AND TESTED
      RomArtifact · ByteSource+OutOfRange · TileCodec · PaletteCodec · AddressMapper ·
      RomPlatformModule · ExtractionManifest+ExtractedAsset · Planar2BppTileCodec ·
      HeaderedCartridgeModule · InvalidCartridgeHeader.  40 tests, exit 0.
      NAMING NOTE: the addendum lists `ByteRange`; the tree calls it `ByteSource`.
      The tree wins, and the addendum's name resolves to nothing.
L4  native Rider projection                                     [~] ASCII, not native UI
      AsciiTileProjection.kt exists and is tested. That is a text projection, not the
      hex view / tile grid / palette / offset linking this rung describes.
```
*L3 before L4, always: the core must be canonical and testable before any IDE
surface projects it. A projection over an unproven core is a demo, not a capability.*

### DONE-2 slice boundary (what ships, what explicitly does not)
```
IN     [x] iNES header detected            HeaderedCartridgeModule; InvalidCartridgeHeader
                                           refuses bad magic (test: "invalid iNES magic is refused")
       [x] CHR ROM located                 chr pages parsed from the header, offset computed
       [x] NES 2bpp tiles decoded          Planar2BppTileCodec.decode_tile, both planes
       [ ] tile grid displayed in Rider    ASCII projection only; no IDE surface
       [ ] click -> tile index + ROM offset  requires the IDE surface; nothing exists
       [x] extraction manifest emitted     ExtractionManifest + ExtractedAsset, traceable
       [x] ROM bytes unmodified            provenance recorded "without mutation" (Kotlin test)
       [x] decoder + parser proof runs     scripts/rf001_slice_proof.py, exit 0.
                                           synthesize -> load -> decode -> manifest ->
                                           display -> integrity as ONE chain, and CALIBRATED:
                                           all 4 sabotage paths correctly fail. Two of them
                                           did NOT at first; fixing that is what makes this
                                           box worth anything. Fixtures stay synthetic and
                                           in-memory; no ROM is read from disk or committed.

OUT    editing · saving modified ROMs · SNES · Genesis · compression ·
       disassembly · emulator integration · patch generation · game-specific hacks
```
*Anything in OUT that appears in a work order is drift, regardless of how small.*

### Build-versus-wrap discipline (standing)
```
[ ] every RetroForge capability classified before work starts:
    WRAP_EXISTING_TOOL · BUILD_IN_CORE · BUILD_IN_PROJECTION ·
    HARDWARE_STORE_CANDIDATE · DEFER · REJECT · REQUIRES_RESEARCH
[ ] mature external tools wrapped, not reimplemented
[ ] core built only where CodeForge needs canonical, testable understanding
```

### ROM legal and safety (HARD — applies to every RetroForge order)
```
[x] only ROMs legally owned, homebrew, or synthetic test fixtures — VERIFIED: zero .nes
        files tracked in any repo; every fixture is constructed in-test from b"NES\x1a"
[x] no copyrighted ROM committed to any repo, ever — verified by the same search
[x] test fixtures are synthetic — b"NES\x1a" + zeroed PRG + hand-made CHR, built at runtime
[ ] source ROM never modified; inspection and editing stay separate paths
[ ] checksums verify source ROM identity before and after every operation
[ ] patches distributed, never modified ROMs
[ ] editing capability gated behind undo/redo and safe-write, not before
```
*This block is closest to HARD LAW in the RetroForge lane. A ROM committed to a
public repo is not revertible in the way a bad merge is — treat it as a
never-automate item alongside publishing.*

---

## ADDENDUM NUMBERS (add to THE FOUR NUMBERS at day close)
```
Tools REGISTERED (not merely installed):   0     (7 INVOCABLE, 0 registered; no registry file)
RetroForge platforms PROVEN:               0     (NES slice runs end to end and is calibrated;
                                                 PROVEN needs the Rider tile grid, 1 of the 2
                                                 remaining IN items)
Rider integration level reached:           L3    (built and tested; L4 is ASCII, not native)
```
