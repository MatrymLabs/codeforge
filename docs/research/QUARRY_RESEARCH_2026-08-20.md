# Quarry research, gathered 2026-08-20

**What this is.** The market research behind the ordering of the Quarry Board, which is
Section 16 of `docs/MASTER_CHECKLIST.md`.

**What this is not.** Doctrine. This file INFORMS Section 16; it does not govern it. It is
dated because research ages and a checklist does not, and because research pasted into a live
checklist quietly becomes law without anyone deciding it. When the hiring signals below stop
being true, this file is still an accurate record of what was believed on its date, which is
the only thing a dated record is ever good for.

**Standing caveat, and it applies to every claim here.** These are hiring-signal observations
drawn from job postings and industry surveys. They are Tier 5 commentary under the authority
tiers, not measurements of this Workshop. No claim below has been verified against CodeForge's
own evidence, and none of it should be cited as a reason a build passed or failed. It is a
reason a build was ORDERED, which is a different and much weaker claim.

---

## The conclusion the ordering rests on

The strongest direction is not a catalog of tutorial projects. It is a deliberately chosen
quarry of real software archetypes that recur in professional work, each reverse engineered
into Blueprints, contracts, Parts, tools, proofs and language lanes.

The distinction matters because current hiring signals emphasise engineers who own software
through design, implementation, testing, deployment, troubleshooting, performance work and
operation, rather than engineers who can demonstrate syntax.

Restated as the question the board actually asks:

```
Not: "What apps can CodeForge generate?"
But: "What recurring classes of engineering problems can CodeForge learn to
      recognise, decompose, build, prove, optimise and reuse?"
```

## Recurring themes across current postings

**End-to-end ownership.** Amazon's SDE postings describe owning software from design through
deployment and operation, with cloud-native architectures, microservices, distributed systems,
CI/CD, monitoring and documentation named explicitly.

**Validating AI-generated code is being named as an engineering skill.** Datadog's current
roles list the ability to validate, critique and refine AI-generated code alongside distributed
systems and debugging. Roblox is hiring at principal level around CI/CD infrastructure,
developer productivity and agentic automation. This is directly relevant: the two-bench process
this Workshop runs is not separate from employability, it is the thing being described.

**Developer tooling is treated as real engineering.** Riot, Activision, Snowflake, JetBrains
and Roblox all currently expose tooling roles: build and test automation, release pipelines,
content authoring tools, IDE integration, Studio tools.

**Distributed systems, reliability and observability recur everywhere.** Datadog and Snowflake
between them cover fault-tolerant services, high-throughput streaming, ingestion,
transformation, telemetry, storage, metadata, replication and query performance.

**Performance engineering remains differentiated.** NVIDIA's C/C++ systems roles cover
kernel/userspace interaction, multithreading, memory behaviour, CUDA tooling, GPU profilers,
benchmarking and optimisation.

**Market context.** The US Bureau of Labor Statistics projects 15% growth for software
developers, QA analysts and testers from 2024 through 2034, roughly 129,200 openings a year.
The game industry is rougher: GDC's 2026 survey of 2,300+ professionals found 28% had been laid
off in the previous two years, 33% among US respondents, and 74% of surveyed students reported
concern about future prospects.

**The conclusion that follows, and it is why the board is not games-only:** train the factory
on the engineering machinery underneath games, SaaS, corporate systems, developer tools,
infrastructure and data systems. Keep a serious game lane; do not stake the portfolio on it.

## Language lanes, mapped to appropriate products

Languages are proven THROUGH products, never through exercises. GitHub's 2025 Octoverse
reported TypeScript overtaking Python and JavaScript in usage in August 2025, with Python still
dominant in AI and data workloads.

```
Python       automation, data pipelines, CLI tools, AI tooling, document processing
TypeScript   web UI, full-stack products, APIs, internal tools
C#/.NET      enterprise APIs, desktop tools, services, Unity tooling
C++          engine systems, performance tooling, game tools, binary processing
Go           infrastructure services, CLIs, networking, control planes
Rust         streaming clients, binary tooling, performance-sensitive libraries
Java         enterprise services, event systems, backend platforms
Kotlin       JVM tooling and Rider/JetBrains plugins
GDScript     Godot gameplay and prototypes
SQL          transactional systems, analytics, migrations, reporting
PowerShell   Windows automation and workstation administration
Terraform    reproducible infrastructure
```

The weak claim is "we built something in 20 languages". The strong claim is "CodeForge
identified the problem, selected appropriate languages and tools, built it, proved it, and
reused known Parts".

## The twenty builds the queue was drawn from

Section 16 takes the first ten. The remainder is recorded here so the ordering is recoverable.

```
 1  Evidence Runner                  makes every later build trustworthy
 2  Developer CLI / scaffolder       automation and developer tooling
 3  Repository health inspector      solves a real daily engineering problem
 4  Excel/CSV -> PDF utility         first clean non-game product
 5  Workshop Operations System       proves ordinary corporate software
 6  API platform                     contracts and integration
 7  Background job queue             durable asynchronous work
 8  Observability stack              operation, not just coding
 9  Event ingestion pipeline         first meaningful distributed system
10  Feature flag service             controlled rollout
11  Usage meter / billing simulator  ledgers, idempotency, event semantics
12  Rider plugin                     IDE and tooling development
13  RetroForge NES inspector         binary, systems and tooling capability
14  Game asset validator             direct production game-tool value
15  Dialogue / quest editor          strong current game-tools hiring signal
16  Localization pipeline            real studio workflow
17  Multiplayer prediction demo      gameplay and systems signal
18  Replay + telemetry system        debugging plus live-service thinking
19  Rust streaming client + binding  systems and polyglot proof
20  CUDA image processing tool       specialist differentiator
```

Builds 1 to 11 establish broad software-engineering credibility. 12 to 18 establish developer
tools and game development. 19 and 20 are specialist depth and belong in the R&D Tech Lab
until they earn their way out.

## The Parts these builds are expected to yield

Recorded as PREDICTIONS, not as a shopping list. A Part enters the Store when a second genuine
consumer exists with a passing proof, and not before.

```
ConfigLoader          CommandRunner        RetryPolicy         BackoffPolicy
StructuredLogger      AuditEvent           AuthenticationAdapter
AuthorizationPolicy   DatabaseMigration    HealthCheck         RateLimiter
PaginationContract    WebhookDispatcher    JobQueue            SchemaValidator
ChecksumVerifier      ArtifactManifest     EvidenceRecord      MetricsEmitter
TracingAdapter        APIClient
```

## What is deliberately NOT on the board

Too shallow to teach the factory anything:

```
calculator, todo list, weather app, static portfolio site, basic blog,
single-table CRUD app, random number game, one-screen platformer,
generic chat UI, generic AI wrapper, RAG chatbot with no evaluation,
URL shortener with no operational depth
```

Too large for useful learning return at this stage, or actively unsafe:

```
custom password hashing, custom cryptography, full Unreal/Unity replacement,
new operating system, new database before CodeForge understands ordinary
database applications
```

The custom-cryptography exclusion is not a scoping preference. It is the security rule, and it
does not move.

## The reverse-engineering record every quarry build produces

Each build is an engineering specimen. The purpose is to teach the factory what the project
IS, not merely to ship it.

```yaml
archetype:
problem:
target_users:
observable_behaviors:
inputs:
outputs:
state:
  authoritative_state:
  transient_state:
  persisted_state:
boundaries:
  user_boundary:
  process_boundary:
  network_boundary:
  storage_boundary:
  external_tool_boundary:
core_components:
contracts:
failure_modes:
language_candidates:
selected_language:
selection_reason:
tools:
existing_parts:
parts_missing:
security_requirements:
performance_requirements:
operability_requirements:
proof_run:
break_tests:
optimization_targets:
harvest_candidates:
```

### Invariants are more reusable than implementations

Examples worth keeping, because each is a real failure class:

```
A payment event is not applied twice.
A retry does not create duplicate work.
A save migration cannot silently delete unknown state.
A source ROM is unchanged during an inspection workflow.
A failed build cannot produce a PASS evidence record.
A client cannot authoritatively grant itself inventory.
A database migration either completes or leaves a recoverable state.
A generated SDK conforms to the same API contract as the server.
```

The fifth is this Workshop's own, and it is the one the Evidence Runner exists to enforce.

### Every archetype needs a planted failure

```
remove permission      corrupt file        drop network        duplicate event
kill worker            saturate queue      break schema        remove dependency
expire token           inject latency      delete required asset
return malformed response
```

The factory proves its instrumentation notices the fault. A gate that has never been shown to
redden is decoration, which is Section 13 of the checklist and canon section 13 saying the
same thing twice.
