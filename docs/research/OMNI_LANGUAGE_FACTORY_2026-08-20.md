# Omni-language Blueprint factory research, gathered 2026-08-20

**What this is.** A research pass on CodeForge as an omni-language Blueprint factory: composable
engineering profiles, a build quarry of roughly 75 candidate specimens, per-language checklist
profiles, compliance profile templates, two-bench prompting patterns, and a staged roadmap.

**What this is not.** Doctrine, a plan, or a queue. Nothing here is scheduled and nothing here is
a decision. It is INTAKE MATERIAL: things we can eventually build, filed so they are recoverable
when their turn comes rather than living in a chat transcript.

**Standing caveat.** The compliance sections are engineering-control templates, not legal
opinions and not substitutes for a qualified assessor. Under the authority tiers this whole file
is Tier 5 commentary. Nothing in it may be cited as a reason a build passed, and no scanner
result here justifies a compliance claim. That constraint is the Workshop rule, and this research
independently reaches the same conclusion.

**Dated because research ages and a checklist does not.** Research pasted into a live governing
document quietly becomes law without anyone deciding it. See Section 16 of MASTER_CHECKLIST.md
for the same separation applied to the Quarry Board.

---

## 1. The central recommendation

Stop trying to build one universal coding checklist. There is no finite checklist for "all
federal requirements" or "all software": applicability changes with language, product shape, data
handled, deployment environment, customer contract and regulatory scope.

Build instead around COMPOSABLE PROFILES, resolved per Blueprint:

```
PRODUCT PROFILE      CLI / web / desktop / game / plugin / service / pipeline
LANGUAGE PROFILE     Python / C# / TypeScript / Java-Kotlin / C-C++ / Rust / Go / SQL / GDScript
SECURITY PROFILE     baseline secure development / internet-facing / privileged / sensitive data
COMPLIANCE PROFILE   Federal-800-53 / CUI-800-171 / PCI / HIPAA / SOC2 / none
TOOL PROFILE         build / test / lint / typecheck / SAST / dependency / secrets / packaging
EVIDENCE PROFILE     JUnit / SARIF / JSON manifest / hashes / provenance / OSCAL where applicable
```

This matches how NIST intends SSDF to work: secure-development practices added to any SDLC rather
than one prescribed stack. Note the version boundary, because it is exactly the kind of thing this
Workshop gets wrong by assumption: SSDF v1.1 is FINAL; v1.2 was published as an initial public
draft in December 2025. A draft is not binding and must not be enforced as though it were.

## 2. Where this research AGREES with what already shipped

Recorded deliberately, because independent agreement is weak evidence and worth labelling as
such rather than treated as confirmation.

- **Four verdicts.** It reserves PASS / FAIL / UNMEASURABLE / NOT_APPLICABLE, and states that a
  missing executable, wrong interpreter, unreadable config or zero-test discovery is UNMEASURABLE
  or FAIL by contract and NEVER PASS. That is the workshop sprint's core rule, reached separately.
- **Task as thin orchestration, language-native tools as leaf truth, a Python CLI for evidence
  and state, PowerShell only for genuinely Windows-specific administration.** That is the layering
  already built in `tools/workshop/` and the Taskfile.
- **Local and CI share the LEAF definitions and the `verify` contract; CI may still carry
  environment plumbing.** That is the ruling made when the canon-path gate proved unpassable in CI.
- **Compliance is entity-level, not code-level.** It states plainly that PCI validation operates
  at an entity/environment level and that passing static scans never makes software "PCI
  compliant". That is the federal hard rule, independently restated.

## 3. Where it CONTRADICTS or complicates current practice

The useful part of any research is where it disagrees.

- **SQL is not one lane.** It argues `sql-postgres`, `sql-sqlserver`, `sql-sqlite` are different
  execution environments and a single generic SQL gate is fiction. The current language-lane model
  treats SQL as one lane. Unresolved; worth a ruling before any SQL lane is claimed PROVEN.
- **GDScript has no built-in pytest equivalent.** It warns against pretending otherwise and says
  the actual test harness must be selected and recorded. Any future Godot lane inherits that.
- **INSTALLED != SUPPORTED, LINTER RAN != PROVEN, HELLO WORLD != PROVEN.** A lane becomes PROVEN
  only when a useful Target Product has moved through Intake, Build, Proof and Delivery. The
  current lane record claims 1 PROVEN and 6 GATED; that claim should be re-tested against this
  stricter bar rather than assumed to survive it.
- **Do not ask an agent to expose private reasoning.** Ask instead for: decision taken, files
  inspected, files changed, commands executed, test output, failed fixture observed, remaining
  uncertainty. Observable engineering evidence, not narrated thought.

## 4. The build quarry, roughly 75 specimens

Sizes are hours (S), days (M), weeks (L) for a proof-oriented version, not commercial completion.
"Hireable" is an INFERENCE from ecosystem signals (Stack Overflow 2025, GitHub Octoverse 2025,
GDC 2026), never a guarantee.

**The recommended first twelve**, chosen so the factory learns CLI tools, files, APIs, SQL, state
machines, binary formats, IDE and game tooling, distributed systems, security evidence and
determinism rather than repeatedly producing CRUD demos:

```
evidence-manifest collector      repository policy checker
Excel-to-PDF converter           CSV ETL pipeline
REST synchronizer                webhook relay
audit-log service                OpenAPI validator
NES CHR inspector                Tiled converter
asset dependency scanner         deterministic replay harness
```

### Game tools

```
sprite-sheet slicer S        texture-atlas packer M       palette validator S
NES CHR inspector M          ROM checksum inspector S     safe ROM patch builder M
save-file inspector M        save migration tool M        tilemap validator S
Tiled-to-engine converter M  localization extractor M     localization gate S
dialogue graph validator M   quest dependency visualizer M
deterministic replay harness L   combat simulation harness M   loot-table analyzer S
asset dependency scanner M   build-size analyzer M        crash-log symbolizer M
shader compilation gate M    scene-performance budget M   screenshot regression M
mod package validator M      game telemetry importer M
```

### Corporate

```
Excel-to-PDF S               CSV schema validator S       CSV/Excel ETL M
SFTP ingestion M             REST synchronizer M          webhook relay/retry M
invoice reconciler M         inventory sync M             scheduled report generator S
audit-log service M          RBAC authorization service L employee onboarding M
configuration drift detector M   document metadata extractor S
sensitive-data redaction L   approval workflow M          KPI dashboard backend M
data-quality dashboard M     feature-flag service M       backup verifier M
file-retention enforcer M    ticket triage integration M  API usage/cost dashboard M
batch job monitor M          data export/deletion workflow M
```

### Developer tools

```
CLI project scaffolder M     repository policy checker M  config-file validator S
custom linter M              formatter L                  test-runner wrapper M
contract-test harness M      OpenAPI validator M          OpenAPI client generator L
DB migration verifier M      dependency vulnerability gate M   SBOM generator M
SARIF aggregator M           evidence-manifest collector M     benchmark regression gate M
fuzz harness generator L     log parser CLI S             git worktree auditor S
multi-repo config sync M     release-note generator S     changelog/API-break gate M
artifact checksum verifier S build provenance emitter L   CI failure classifier M
```

Several of these already exist here in some form: the git worktree auditor is the stranded gate,
the repository policy checker is the register and claims gates, the evidence-manifest collector is
Crank 1. That overlap is a CONSUME-FIRST signal, not a coincidence, and any of these entering the
queue must be screened against what is already built.

## 5. The universal language profile

Required fields regardless of language:

```yaml
language_profile:
  toolchain_version:
  dependency_lock:
  restore_or_sync:
  build:
  format_check:
  lint:
  typecheck:
  unit_test:
  integration_test:
  security_scan:
  dependency_scan:
  secrets_scan:
  package:
  run:
  negative_fixture:
  artifact_globs:
  evidence_formats:
  known_suppressions:
  suppression_reason_required: true
  gate_calibrated_on:
```

`negative_fixture` and `gate_calibrated_on` are the two that matter most here, and they encode
canon 13: a gate is trusted only when it has been shown to fail.

Per-lane baselines, condensed:

```
Python     uv lock --check; uv sync --locked; ruff format --check; ruff check; mypy; pytest; uv build
C#/.NET    dotnet restore/build/format --verify-no-changes/test    (record WHICH runner: VSTest or
           Microsoft.Testing.Platform, new in .NET 10, produced the evidence)
TS/Node    locked install; tsc --noEmit; lint; node:test or npm test; build
Java/Kotlin Gradle Wrapper; gradlew clean check; detekt; ktlint; optional Kover
C/C++      CMake; ctest; clang-format --dry-run --Werror; clang-tidy; ASan/UBSan
Rust       cargo fmt --check; cargo check; cargo clippy -D warnings; cargo test; cargo audit/deny
Go         gofmt; go vet; golangci-lint; go test; govulncheck (reachability-aware)
SQL        per-engine, NOT generic: parser/migration validation against a disposable DB
GDScript   pin Godot; headless import/load; typed profile; a NAMED test harness, not an assumed one
```

## 6. Compliance profiles

Selected at Intake, never assumed. The anti-pattern this exists to prevent:

```
Run scanner. Scanner green. Declare HIPAA / PCI / federal compliance.
```

```
NIST 800-53      federal system or customer control mapping. Controls are TAILORED, never
                 copied wholesale. Families: AC, AU, CM, IA, IR, RA, SA, SC, SI, SR.
NIST 800-171     applies specifically when a NONFEDERAL system handles CUI. Rev. 3 finalized
                 May 2024, assessment procedures in 800-171A. A DIFFERENT profile from 800-53.
PCI DSS 4.0.1    entities that store/process/transmit cardholder data or can affect the CDE.
                 Validation is entity-level. Software is never "PCI compliant" from a scan.
HIPAA Security   covered entities and business associates handling ePHI. The January 2025
                 cybersecurity strengthening rule is still PROPOSED and must be held as a
                 future/draft profile, not enforced as current law.
SOC 2            an AICPA ATTESTATION over Trust Services Criteria, not a statute and not a
                 federal coding standard.
```

Blueprint shape:

```yaml
compliance:
  profiles: [secure_dev_base, owasp_asvs_5, hipaa_security]
  applicability:
    ephi: true
    cardholder_data: false
    cui: false
  controls:
    not_applicable:
      - id: pci
        reason: "No payment-account data or CDE impact."
  evidence_retention: defined
  assessor_required: true
```

Note `not_applicable` carries a REASON. That is the Universal Clause rule: applicability is
resolved, never assumed, and a control that does not apply is marked with a recorded reason rather
than silently skipped.

## 7. Evidence formats: adopt, do not force

No single existing standard represents a Workshop proof run. The recommendation is a small custom
envelope that REFERENCES native artifacts:

```
SARIF 2.1.0   OASIS standard, for STATIC-ANALYSIS findings. Not a universal run manifest.
JUnit XML     test-run outcomes. Keep as an artifact, not as the envelope.
OSCAL         NIST assessment results. Disproportionate for "did ruff run this morning".
SLSA/in-toto  build provenance. Borrow the concepts now; real attestations belong to
              release-grade artifacts later.
```

That is adoption plus a small envelope, not reinvention. It matches what Crank 1 already built.

## 8. Staged roadmap

```
Stage 0  Baseline Held        all declared tools execute; known-red fixtures redden;
                              no hidden zero-test or wrong-interpreter pass
Stage 1  Crank Turns          Intake -> Blueprint -> Work Order -> build -> independent proof
Stage 2  Generality           three materially different outputs through the same loop
Stage 3  Intake is Software   a submitted form generates a valid Blueprint and agent-ready orders
Stage 4  Omni-language Ladder one real product per lane; each reaches PROVEN with a calibrated
                              break test, not merely an installed toolchain
Stage 5  Factory Projection   a management interface over proven factory state, not a second
                              source of truth
```

## 9. The governing checklist this research proposes

Kept verbatim because its value is the ORDER of the questions:

```
[ ] What are we building?                    [ ] Who uses it?
[ ] What data does it touch?                 [ ] Which compliance profiles actually apply?
[ ] Which language lanes apply?              [ ] Are those lanes GATED or PROVEN?
[ ] Which Hardware Store Parts solve pieces already?
[ ] Which external tools should be consumed rather than reinvented?
[ ] What invariant must survive?             [ ] What is the written 80% bar?
[ ] What Break Test must redden?             [ ] What Proof Run is written BEFORE implementation?
[ ] Which Bench builds?                      [ ] Which Bench independently verifies?
[ ] Did every required tool actually execute?
[ ] Were test-discovery counts plausible?
[ ] Did scanners run against calibrated known-hit fixtures?
[ ] Are suppressions counted and justified?
[ ] Are evidence artifacts hashed and timestamped?
[ ] Is the output runnable by the requester?
[ ] Are Known Limitations explicit?
[ ] What did we reverse engineer from the resulting code?
[ ] What was reimplemented?  What recurred?  What is generalizable?  What caused friction?
[ ] Does anything qualify as a Hardware Store candidate?
[ ] What before/after measurement supports any optimization claim?
[ ] What is the next Work Order?
```

## 10. The endpoint, in one line

CodeForge should not learn every programming language as trivia. It should learn the finite set of
recurring engineering systems from which applications are assembled, bind each to language, tool,
security and compliance profiles, dispatch bounded work to two benches, require positive AND
negative proof, reverse engineer what came out, and convert what recurs into Parts.
