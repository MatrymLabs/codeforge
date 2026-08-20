# Build catalog source table, 2026-08-20

**What this is.** The verbatim source for `catalog/builds.yaml` (WO CF-CATALOG-001). Every row
carries the six fields the catalog schema needs: name, domain, size, lanes, proof criterion, why,
potential users.

**Why it is a separate file from OMNI_LANGUAGE_FACTORY_2026-08-20.md.** That file is ANALYSIS and
condenses these rows into grouped lists. This file is DATA and must not be condensed. A
transcription order pointed at the analysis would force the implementer to invent the missing
per-row fields, which is exactly what "transcribe exactly, do not invent" forbids.

**Sizes.** S = hours, M = days, L = weeks, for a focused proof-oriented version, not commercial
completion.

**"Hireable" is an INFERENCE** from ecosystem signals (Stack Overflow 2025, GitHub Octoverse 2025,
GDC 2026), never a guarantee of employment. The `why` column carries that inference and should be
read as such.

---

## Game tools

| Project | Size | Suggested lanes | Proof criterion | Why useful | Potential users |
|---|---|---|---|---|---|
| Sprite-sheet slicer | S | Python/C# | Known atlas produces exact tiles plus metadata | Asset-pipeline fundamentals | Indie/AAA tools teams |
| Texture-atlas packer | M | C#/Rust | Pack fixtures deterministically; no overlaps | Real content tooling | Game studios |
| Palette validator | S | Python/Rust | Reject out-of-profile colors | Retro/pixel pipelines | Artists/tools programmers |
| NES CHR inspector | M | Kotlin + Rust/C# | Known ROM produces exact decoded tiles/offsets | Binary parsing plus IDE tooling | Retro developers |
| ROM checksum/metadata inspector | S | Rust/Go/Python | Known fixtures identify format/hash | Reverse-engineering discipline | ROM/homebrew tooling |
| Safe ROM patch builder | M | Rust/C# | Source checksum plus patch produces expected target | Binary transformation | Homebrew/mod teams |
| Save-file inspector | M | C#/Rust | Decode/re-encode fixtures losslessly | Serialization/reverse engineering | QA/modders |
| Save migration tool | M | C#/Python | Old save to new schema with invariants | Versioning/migrations | Live game teams |
| Tilemap validator | S | Python/C# | Bad references/collisions redden | Content validation | Level designers |
| Tiled-to-engine converter | M | C#/Python | TMX fixture produces deterministic engine data | Pipeline integration | 2D teams |
| Localization extractor | M | Python/C# | Source assets produce complete key catalog | Production localization | Game/content teams |
| Localization completeness gate | S | Python | Missing/duplicate keys fail | CI content quality | Localization teams |
| Dialogue graph validator | M | C#/GDScript | Detect unreachable/cyclic-invalid nodes | Narrative tooling | RPG studios |
| Quest dependency visualizer | M | TypeScript/C# | Fixture graph produces expected dependency graph | Graph/data UI skills | Designers |
| Deterministic replay harness | L | C++/C#/GDScript | Same input stream produces same state/hash | High-value gameplay/QA skill | Engine/gameplay teams |
| Combat simulation harness | M | Python/C# | Seeded simulations reproducible | Balancing/testing | Systems designers |
| Loot-table analyzer | S | Python | Distribution within tolerance | Probability plus analytics | Economy designers |
| Asset dependency scanner | M | C#/Python | Detect orphan/missing/cyclic assets | Build optimization | Tools/build teams |
| Build-size analyzer | M | Python/Go | Explain artifact-size deltas | Shipping optimization | Console/mobile teams |
| Crash-log symbolizer frontend | M | C++/C#/Python | Fixture addresses resolve to symbols | Debug tooling | Engine teams |
| Shader compilation gate | M | C++/C# | Invalid fixtures fail, valid shaders compile | Rendering pipeline exposure | Graphics teams |
| Scene-performance budget checker | M | GDScript/C# | Fixture scene exceeding budget reddens | Performance discipline | Godot/Unity teams |
| Level screenshot regression tool | M | Python/C# | Changed reference view detected | Visual QA | QA/art teams |
| Mod package validator | M | Rust/C# | Package schema/hash/dependencies verified | Extensibility systems | Mod-friendly studios |
| Game telemetry importer | M | Go/Python/SQL | Events ingest, deduplicate and query | Backend plus game analytics | Live-services teams |

## Corporate

| Project | Size | Suggested lanes | Proof criterion | Why useful | Potential users |
|---|---|---|---|---|---|
| Excel-to-PDF converter | S | Python/C# | Workbook fixture produces readable PDF; source unchanged | Useful automation specimen | Finance/admin teams |
| CSV schema validator | S | Python/Go | Invalid types/columns fail | ETL/data-engineering basics | Data teams |
| CSV/Excel ETL pipeline | M | Python/SQL | Fixture produces transformed rows plus audit totals | Everyday enterprise work | Analytics/operations |
| SFTP ingestion service | M | Go/C# | Fixture files transfer once, resume safely | Integration engineering | B2B enterprises |
| REST API synchronizer | M | C#/Go/TypeScript | Two systems converge idempotently | Common SaaS integration | Enterprise/SaaS |
| Webhook relay/retry service | M | Go/TypeScript | Retries, dedupe and signatures proven | Distributed systems skill | SaaS/platform teams |
| Invoice reconciler | M | Python/SQL | Fixture invoices/payments match exceptions | Finance automation | Accounting/ERP teams |
| Inventory synchronization service | M | C#/Go/SQL | Conflicts resolved by written rule | Integration/data consistency | Retail/manufacturing |
| Scheduled report generator | S | Python/C# | Dataset produces reproducible PDF/email artifact | Practical automation | Operations |
| Audit-log service | M | Go/C#/SQL | Events append, query and resist mutation | Security/compliance portfolio | SaaS/regulated teams |
| RBAC authorization service | L | C#/Java/Go | Allow/deny matrix proves policies | Enterprise backend skill | Identity/platform teams |
| Employee onboarding automation | M | Python/PowerShell | Fixture user produces exact account/task plan | IT automation | Corporate IT |
| Configuration drift detector | M | Go/Python | Changed machine/config detected | Ops/platform work | IT/SRE |
| Document metadata extractor | S | Python | PDF/Office fixtures produce normalized metadata | Document workflows | Legal/operations |
| Sensitive-data redaction pipeline | L | Python/C# | Known sensitive fixtures redacted; negatives preserved | Regulated-data engineering | Healthcare/legal |
| Approval workflow service | M | TypeScript/C#/SQL | State transitions and permissions proven | Business-app architecture | SaaS/internal apps |
| KPI dashboard backend | M | TypeScript/C#/SQL | Seed data produces exact metrics/API | Full-stack/data skills | Management/BI |
| Data-quality dashboard | M | Python/SQL/TS | Bad rows surfaced with rule IDs | Analytics engineering | Data teams |
| Feature-flag service | M | Go/C#/TS | Deterministic targeting plus rollback | Platform engineering | SaaS/product teams |
| Backup verifier | M | Python/Go | Restore fixture and compare hashes | Reliability/SRE | IT/SRE |
| File-retention enforcer | M | Python/PowerShell | Expired fixtures identified; dry-run first | Governance automation | Records/IT |
| Ticket triage integration | M | Python/TS | Fixture tickets classify/route deterministically | Workflow automation | Support/IT |
| API usage/cost dashboard | M | Go/TS/SQL | Seed events aggregate correctly | FinOps/platform | Cloud/SaaS |
| Batch job monitor | M | Go/Python | Hung/failed/success states accurately reported | Ops observability | Data/IT |
| Data export/deletion workflow | M | C#/Python/SQL | Subject fixture exported/deleted per policy | Privacy engineering | SaaS/compliance |

## Developer tools

| Project | Size | Suggested lanes | Proof criterion | Why useful | Potential users |
|---|---|---|---|---|---|
| CLI project scaffolder | M | Go/Rust/Python | Fixture input produces exact tree; rerun safe | Tooling portfolio | Developer-platform teams |
| Repository policy checker | M | Python/Go | Broken repo fixture fails named rules | Platform governance | DevEx teams |
| Config-file validator | S | Rust/Go/Python | Bad YAML/JSON/TOML rejected | Universal tooling skill | Any engineering team |
| Custom linter | M | Rust/Go/Python | Planted violations produce locations/codes | Compiler/static-analysis exposure | Tooling teams |
| Formatter | L | Rust/Go | Idempotency: format twice equals same bytes | Parsing/transformation skills | Language/tool teams |
| Test-runner wrapper | M | Python/Go | Zero tests is not success; correct exit mapping | CI reliability | DevEx/QA |
| Contract-test harness | M | Python/TS/C# | Producer/consumer fixtures agree or fail correctly | Microservice testing | Platform teams |
| OpenAPI validator | M | TypeScript/Go | Breaking fixture fails contract gate | API governance | Backend/platform |
| OpenAPI client generator | L | Go/Rust/TS | Spec produces compiling client plus fixture tests | Code generation | SDK/platform teams |
| Database migration verifier | M | Python/Go/SQL | Apply then rollback, or forward migration, proven | Backend/DB engineering | SaaS |
| Dependency vulnerability gate | M | Go/Python | Known vulnerable fixture reddens | AppSec/CI | Security/platform |
| SBOM generator/normalizer | M | Go/Rust | Build fixture produces complete SPDX/CycloneDX artifact | Supply-chain security | Federal/enterprise |
| SARIF aggregator | M | Go/Python | Multiple tool SARIF produce normalized findings | Security automation | AppSec |
| Evidence-manifest collector | M | Python/Go | Capture command, version, SHA, artifact hashes, verdict | Core CodeForge capability | Regulated engineering |
| Benchmark regression gate | M | Rust/Go/Python | Known slowdown crosses threshold | Performance engineering | Platform/game/backend |
| Fuzz harness generator | L | Rust/C++/Go | Seed corpus finds planted parser bug | Security/reliability | Systems/AppSec |
| Log parser/query CLI | S | Go/Rust/Python | Mixed fixture produces structured records | Ops/tooling | SRE/developers |
| Git worktree auditor | S | Go/Python | Detect stranded/unpushed fixture branches | Workflow automation | Dev teams |
| Multi-repo config synchronizer | M | Go/Python | Drift detected; update idempotent | Platform engineering | Monorepo/polyrepo teams |
| Release-note generator | S | Python/Go | Commits/PR fixture produce deterministic notes | Release engineering | Any team |
| Changelog/API-break gate | M | Go/Rust | Public API change without note fails | Library governance | SDK teams |
| Artifact checksum verifier | S | Rust/Go | Corruption fixture fails SHA-256 | Supply-chain fundamentals | Build/release teams |
| Build provenance emitter | L | Go/Rust | Artifact bound to source/build metadata | Modern supply-chain portfolio | Federal/enterprise |
| CI failure classifier | M | Python/Go | Fixture logs distinguish test, tool and infra failure | CI productivity | DevEx/SRE |

---

## The recommended first twelve

Named in the source as the highest-value opening set, because together they force the factory to
learn CLI tools, files, APIs, SQL, state machines, binary formats, IDE and game tooling,
distributed systems, security evidence and determinism rather than repeatedly producing CRUD
demos:

```
evidence-manifest collector      repository policy checker
Excel-to-PDF converter           CSV ETL pipeline
REST synchronizer                webhook relay
audit-log service                OpenAPI validator
NES CHR inspector                Tiled converter
asset dependency scanner         deterministic replay harness
```

## The reverse-engineering taxonomy

Nine classes, verbatim. Every delivered piece is classified as exactly one:

```
TARGET_PRODUCT_ONLY
LANGUAGE_LANE_PATTERN
TOOL_ADAPTER
TEST_FIXTURE
VALIDATOR
GENERATOR
HARDWARE_STORE_CANDIDATE
KNOWN_FAULT
CASE
```

## CONSUME-FIRST WARNING for whoever transcribes this

Several rows describe capabilities that ALREADY EXIST in this Workshop. Transcribe them anyway,
because the catalog records the problem class rather than the implementation, but any entry
reaching ACTIVE must be screened against what is built before a single line is written:

```
Git worktree auditor          -> ship/scripts/stranded_gate.py exists and is calibrated
Repository policy checker     -> ship/scripts/register_gate.py and claims_gate.py exist
Evidence-manifest collector   -> tools/workshop/evidence/ exists (Crank 1)
Multi-repo config synchronizer-> partially covered by matrym-devconfig
Test-runner wrapper           -> the pytest exit-5 mapping already lives in
                                 tools/workshop/checks/adapters.py
```

That overlap is a consume-first signal, not a coincidence. A catalog entry is a MENU ITEM, and
ordering one that is already on the table is how the Store fills with duplicates.
