# The Road to the Factory (v2)
## From baseline to the omni-language Blueprint factory

This document is the anchor for the next phase of CodeForge.

CodeForge is becoming the omni-language Blueprint factory.

Not Python-only. Not C#-only. Not game-only. Not web-only. Not text-only.
Not tied to one runtime, tool, projection, or language.

If it can be coded, CodeForge should eventually be able to intake the request,
configure a Blueprint, pull from the Hardware Store, assign the right Benches, build
the Target Product, prove the result, deliver the working output, and harvest reusable
Parts back into the Workshop.

---

## 1. Vision

A requester should eventually be able to say:

I need an Excel-to-PDF converter.
I need a 2D pixel RPG prototype.
I need an SMS-based classroom quiz game.
I need a Rider plugin that inspects NES graphics.
I need a MUD world with account login, characters, combat, and persistence.

and CodeForge turns that request into a structured Blueprint that defines what is
being built, which languages and tools are required, which Hardware Store Parts
apply, which contracts prove the output, which Benches work on it, which agent
receives which Work Order, which Proof Run establishes the working bar, and which
Parts should be harvested afterward.

The goal is not perfect software in one pass. The goal is a reliable factory loop
that produces a working, inspectable, testable, improvable 80 percent solution, and
then improves it through evidence.

## 2. The Core Factory Loop

INTAKE — the need is captured as a structured request.
CONFIGURE — the request becomes a Blueprint: language lanes, tools, Parts, contracts,
Work Orders, and the Proof Run that will judge it.
BUILD — the Benches produce the Target Product from the Blueprint.
PROVE — gates, contract tests, and the prewritten Proof Run establish that the output
works to the stated bar.
DELIVER — the requester receives a working output that can be run, inspected, improved.
HARVEST — evidence reveals reusable Parts for the Hardware Store.
OPTIMIZE — measured improvement of a working output.
CONTINUE — the next Work Order is already clear.

Everything else exists to make this loop wider, faster, safer, and more repeatable.

## 3. The 80 Percent Bar

The bar is not a feeling. It is a written, testable statement made at INTAKE and
judged by a Proof Run written at CONFIGURE, before any code exists.

Three rules:

The bar is stated at intake in one sentence a non-engineer could check.
The Proof Run that judges it is written at CONFIGURE time, never after the build.
A criterion written after seeing the output is not a criterion, it is a justification.

The remaining 20 percent is never silently dropped. At DELIVER, every known shortfall
is written down as a Known Limitation with one line each. Each limitation is a
candidate for a follow-on intake. A delivery with no limitations listed is a delivery
that was not inspected.

## 4. The Omni-Language Rule

Any language. Any stack. Any product type. One Blueprint factory.

The Workshop's candidate lanes include Python, C#, F#, Visual Basic, C, C++, Java,
Kotlin, JavaScript, TypeScript, Node.js, React, React Native, HTML, CSS, SCSS, Sass,
SQL, JSON, YAML, XML, Markdown, OpenAPI, shell, PowerShell, Terraform, GDScript,
Godot C#, Unity C#, Unreal C++, ASP.NET, Razor, Blazor, XAML, EF Core, .NET Aspire.

**None of these are supported by appearing on this list.** A language is a candidate
until a Language Lane record exists with proven commands and a calibrated gate. Listing
is not support. Invisible language use is drift.

## 5. Language Lanes

Each supported language or stack is a Language Lane. A lane record holds:

language_lane_id, display_name, ecosystem, primary_tools, build_command, test_command,
format_command, lint_command, typecheck_command, package_manager, runtime,
common_project_shapes, supported_output_types, known_risks, security_notes,
optimization_notes, hardware_store_parts, proof_run_templates, gate_calibrated_on,
status.

Example lanes: python, csharp-dotnet, kotlin-jvm, typescript-node, gdscript-godot,
cpp-native, sql-postgres, terraform-infra, markdown-docs, openapi-contracts.

A lane's status is one of CANDIDATE (named only), INSTALLED (toolchain present),
GATED (lint/typecheck/test wired), or PROVEN (a real Target Product shipped in it).
`gate_calibrated_on` records the date the lane's gate was last shown to redden on a
planted violation. An uncalibrated lane is not GATED.

A Language Lane is how the factory knows how to build, test, optimize, and verify work
in that ecosystem.

## 6. Hardware Store Role

The Hardware Store is separate from CodeForge, and CodeForge depends on it.

At CONFIGURE, the factory asks: have we built something like this before, is there a
Part, adapter, validator, generator, fixture, or pattern to consume, which lanes have
implementations, which Parts are verified, which are candidates, which have two or more
genuine consumers.

At HARVEST, the factory asks: did this solve a problem we have seen before, did we
reimplement something, do two products now need the same capability, is this a Part
candidate, does it need R&D review, does it need a new language adapter, does the
Store need a new contract fixture.

Every Blueprint searches the Store before building.

Every Bench Report records reusable Part signals: reimplemented, recurrence,
generalizable, friction. If nothing was observed, write "none observed." Blank signals
are not allowed.

A Part is promoted from candidate to certified when a second genuine consumer exists
and both consumers' proofs pass against it. One consumer is a library; two are a Part.

## 7. What the Factory Does Not Build

A factory that claims to build anything is unfalsifiable and unsafe. CodeForge refuses,
at intake, any request where an 80 percent solution is dangerous rather than merely
incomplete:

Safety-critical control systems.
Medical diagnosis, dosing, or treatment decisions.
Financial, legal, or tax advice presented as authoritative.
Novel cryptography or authentication primitives (consume proven Parts instead).
Anything requiring regulatory certification the Workshop cannot obtain.
Anything whose failure mode injures a person or destroys unrecoverable data.

Refusal is recorded in the intake with the reason. This list is short on purpose and
changes only by the Principal Engineer's decision.

## 8. Intake Form

The Intake Form is the bridge between a human need and a buildable Blueprint. It begins
as YAML and may later become a UI.

**Required core (v1 — a request is valid with these ten fields and nothing else):**

```
request_id
request_title
requester
plain_language_request
expected_output
acceptable_80_percent_solution     # the bar, one checkable sentence
output_type.category
output_type.delivery_format
language_lanes.preferred
size_estimate                      # S (hours) / M (days) / L (weeks)
```

Everything below is progressive: filled when known, expanded during CONFIGURE, never a
barrier to submitting a request. A form nobody can finish is a form nobody uses.

**Progressive fields:**

product_goal: target_user, problem_solved, success_definition
output_type: examples, must_run_on, nice_to_have_platforms
language_lanes: allowed, forbidden, multi_language_required, reason_for_choice
design_type: app_type, interface_type, data_type, runtime_type, integration_type,
deployment_type
inputs: files, APIs, databases, user_inputs, external_tools, sample_data
outputs: files, executables, services, docs, tests, reports, packages, assets
hardware_store: required_search_terms, candidate_parts, parts_to_consume,
adapters_needed, validators_needed, generators_needed, fixtures_needed
tool_utilization: IDE, command_line_tools, build_tools, test_tools, analysis_tools,
optimization_tools, deployment_tools, AI_agents, external_tools
contracts: required_behaviors, invariants, failure_cases, acceptance_tests, proof_run,
break_tests
handoffs: codex_work, claude_code_work, human_review, blocked_until, approval_gates
security: secrets, data_sensitivity, permissions, threat_notes, unsafe_operations
optimization: performance_goal, memory_goal, size_goal, UX_goal, maintainability_goal,
code_quality_goal, refactor_budget
delivery: output_location, run_instructions, proof_required, demo_required,
outside_user_possible
harvest: reusable_signals_expected, hardware_store_candidate_likely,
language_lane_update_needed

## 9. Blueprint

The Intake Form captures what the requester wants. The Blueprint defines how CodeForge
will build it. It is not documentation; it must be capable of driving Work Orders.

blueprint_id, blueprint_version, source_request_id, target_product_name,
target_product_type, language_lanes, architecture, modules, hardware_store_parts,
tools, work_orders, contracts, proof_runs, delivery_artifacts, harvest_plan,
known_risks, known_limitations, principal_engineer_decisions, anchor.

## 10. Blueprint Evolution and Regeneration

This is the question every generator-based system gets wrong, so it is answered here
before it is built.

**Ownership split, permanent:**

The Blueprint owns structure, contracts, Parts list, tool declarations, and Proof Runs.
The Target Product owns implementation.

**Regeneration rule:** running a Blueprint again may create or update scaffold,
contracts, fixtures, and configuration. It never overwrites implementation files. Files
the factory generated and the requester never touched are refreshable; files with human
or Bench edits are appended to, flagged, or left alone, never replaced silently.

**Change rule:** a Blueprint change after delivery increments blueprint_version and
carries a one-line migration note describing what a rebuilt product would gain or lose.

A Blueprint whose product has drifted so far that regeneration is meaningless is
recorded as SUPERSEDED, and the product becomes its own source of truth with a dated
note explaining why. That is an acceptable outcome, recorded rather than discovered.

## 11. Target Product

A Target Product can be a script, library, CLI tool, desktop app, web app, mobile app,
Rider plugin, game, MUD, 2D game, 3D game, ROM asset tool, classroom system,
automation service, compliance tool, API, database-backed application, static site,
documentation package, test harness, or data converter.

The factory does not care whether the output is a game. It cares whether the Blueprint
can be built, proven, delivered, and harvested.

**Delivery location rule:** each Target Product is delivered to a stated location
declared at intake. A product expected to grow gets its own repository; a product that
is one artifact is delivered into the requesting Blueprint's `dist/`. The choice is
made at CONFIGURE and written into the Blueprint, so repository sprawl is a decision
rather than an accident.

## 12. Source Truth and Projection

The underlying Blueprint, rules, assets, state, tests, and evidence are the durable
engineering material. The interface is a projection. Text, graphical, Rider, web, test,
and admin projections are all different ways of working with the same Blueprint.

**Projection fidelity is proven, not assumed.** Any product with more than one
projection carries a differential proof: the same operations run through each
projection produce the same underlying state. A projection that cannot be differenced
against source truth is a projection nobody should trust.

A differential that cannot execute reports UNMEASURABLE. A crash is not a test result.

## 13. Handoffs to Codex and Claude Code

CodeForge generates Work Orders from the Blueprint. The agents receive Bench-ready
Work Orders, never vague prompts.

**Codex — implementation-heavy work:** core logic, data models, persistence, commands,
transactions, test harnesses, parsers, decoders, generators, validators, language
adapters, build scripts, proof machinery, integration code.

**Claude Code — shaping and verification:** architecture, Build Sheet authoring, UI and
presentation, client flow, accessibility review, Bench Report review, independent
verification, developer experience, documentation, scaffold planning, contradiction and
gap review.

**Standing rule:** the Bench that builds an instrument never certifies it. Calibration
is always performed by the other Bench.

**Every Work Order carries, without exception:**

Anchor (what the Workshop is building right now — an order without one is
undispatchable)
Goal
Invariant
Scope
Non-goals
Repository
File allowlist
Bench claim
Language (one per order)
Hardware Store search
Contract tests
Expected Break Test
Definition of done
Proof Run command
Rollback
Approval gates
Size (S/M)
Reusable Part signals

## 14. Tool Utilization

Tool use is part of the build, not an afterthought. A Blueprint specifies IDE tools,
command line tools, language runtimes, package managers, test frameworks, formatters,
linters, type checkers, profilers, security scanners, build systems, database tools,
asset tools, deployment tools, and AI agents.

Examples: Rider, Godot, Aseprite, Tiled, dotnet CLI, Gradle, npm, pytest, xUnit, Jest,
Ruff, mypy, ESLint, tsc, PostgreSQL, Docker, GitHub Actions.

The factory asks: what tools does this product require, which are already in the
Hardware Store, which require setup, which require a proof command, which require a
Break Test, which introduce risk.

**A tool is not integrated because it is installed.** Installed is not invocable. A
tool counts as available only when a command has been run through it and its output
captured.

## 15. Multi-Code Utilization

A single Blueprint may use multiple languages.

Rider plugin: Kotlin frontend, Java platform APIs, YAML manifests, Markdown docs,
Gradle build.
2D online game: C# server, Godot C# or GDScript client, PostgreSQL schema, YAML
content, JSON network messages, Markdown docs.
Excel-to-PDF converter: Python or C#, CLI wrapper, YAML config, test fixtures,
Markdown docs.

A Blueprint defines per lane: language, role, owner, build_command, test_command,
proof_run, hardware_store_parts.

Multi-code means the right tool goes to the right Bench. It does not mean one Work
Order spans two languages — orders remain single-language, always.

## 16. Optimization

Every Target Product eventually passes an Optimization Pass. Optimization is not
premature micro-optimization; it is making the output better according to the product
goal: performance, memory, startup time, bundle size, binary size, readability,
maintainability, testability, accessibility, security, error handling, developer
experience, user experience, deployment simplicity.

The pass asks what is slow, wasteful, fragile, hard to read, hard to test, overbuilt,
underbuilt, duplicated, and what should become a Hardware Store Part.

**No optimization claim without a before measurement and an after measurement, both
captured.**

## 17. When a Build Fails

Not every Blueprint produces a product. A factory without a scrap path lies about its
yield.

A Blueprint is recorded FAILED when its Proof Run cannot pass within the stated size
estimate, or a precondition proves unobtainable, or the request is discovered to be out
of scope per section 7.

A failed Blueprint still harvests. The record captures: where it failed, what was
learned, which assumption was wrong, which Part was missing that would have saved it,
and whether a lane, tool, or Part gap caused it. Failure records are read at CONFIGURE
of similar requests.

A failed Blueprint is not deleted and not quietly abandoned. It is closed with a reason,
the same as a killed Work Order.

## 18. Execute Posture

Baseline is the floor, not the destination.

The posture is: execute, prove, continue.

The factory does not stop after tests pass once, baseline is held, a scaffold exists, a
document is written, a module is created, or a prompt is generated. It keeps turning the
crank until a Target Product exists, the output runs, the Proof Run is captured, the
requester can use it, the reusable signals are recorded, and the next Work Order is clear.

Baseline held. Crank turns. Output delivered. Parts harvested. Next build.

**The known failure mode, named:** system-building is more comfortable than shipping,
and produces a more satisfying ledger. This document is itself an artifact of that pull.
The counter-rule is the exit proofs below — no stage advances on a document, only on a
captured execution.

## 19. Honest Gap Map

| Factory piece | State today |
|---|---|
| Build discipline, gates, evidence | Real |
| Blueprint as buildable unit | Exists conceptually, needs end-to-end proof |
| Omni-language capability | Mandate real, proven in Python only |
| Hardware Store | Real structure, needs language-lane expansion |
| Intake Form | Missing |
| Blueprint generation from form | Missing |
| Blueprint regeneration and versioning | Ruled here, unbuilt |
| Multi-language Work Orders | Emerging, not fully proven |
| Tool utilization registry | Missing |
| Optimization Pass | Missing |
| Failure/scrap path | Ruled here, unbuilt |
| Non-game Blueprint proof | Needed |
| Projection fidelity proof | Exists for the engine seam only |
| MUD as management projection | Vision, stays later |
| External user of output | Zero. The counter runs. |

## 20. Factory Stages

Every stage exits on a captured execution, never a document.

**Stage 0 — Baseline Held.** Prove the floor is trustworthy before expanding.
Exit: baseline Proof Run captured, known skips visible, known faults visible, no hidden
red state.

**Stage 1 — The Crank Turns Once.** One Blueprint produces one working output. The
Blueprint may be hand-authored.
Exit: Blueprint builds, output runs, state persists if relevant, Proof Run captured,
Bench Report completed.

**Stage 2 — Generality Proof.** A second Target Product unlike the first. Candidate:
the Excel-to-PDF converter — small, useful, non-game, clear inputs and outputs,
showable to an outside human.
Exit: second Target Product through the same loop, and used once by someone other than
the founder.

**Stage 3 — Intake Becomes Real.** The YAML Intake Form, and a Blueprint generated
from it.
Exit: a third Target Product that starts from an Intake Form rather than a
hand-authored Blueprint.

**Stage 4 — Language Ladder.** Prove omni-language one lane at a time: Python utility,
C# service, TypeScript web output, GDScript or Godot C# 2D client, Kotlin Rider plugin,
SQL-backed application, shell or PowerShell automation, Terraform output.
Exit per rung: working Target Product, language-specific Proof Run, lane record moved
to PROVEN with a calibration date, reusable signals recorded.

**Stage 5 — Factory Floor Projection.** The world interface as a management projection
of the factory. Stays last on purpose. Projection follows product.
Exit: one real Work Order dispatched and verified from inside the world projection.

**Layers, not stages.** Tool utilization (§14), optimization (§16), and the failure path
(§17) are present in minimal form from Stage 1 and formalized as the factory widens.
Naming them as later stages would defer them forever. From Stage 1: every Blueprint
lists its tools, every delivered product gets one measured optimization observation,
and every failure is recorded.

## 21. What This Road Refuses

No stage skips its exit proof.
No language is supported because it is named.
No tool is integrated because it is installed.
No Part is trusted without two consumers and passing proofs.
No Work Order is valid without an anchor, scope, invariant, allowlist, and proof.
No Proof Run is written after the build it judges.
No optimization claim without before and after measurements.
No delivery without its Known Limitations listed.
No failed Blueprint quietly abandoned.
No AI agent gets vague build instructions.
No product stops at scaffold unless scaffold was the stated output.
No baseline celebration replaces execution.
No MUD projection before the factory exists.
No Aethryn-centered definition of CodeForge. Aethryn is one possible output.
CodeForge is the factory.

## 22. Immediate Implementation Needs

Intake Form v1 schema (required core plus progressive fields).
Blueprint v1 schema, including version and regeneration ownership.
Language Lane registry with status and calibration date.
Tool Utilization registry.
Hardware Store language-lane records.
Work Order generator from Blueprint, anchor-bearing.
Codex handoff template.
Claude Code handoff template.
Optimization Pass template.
Failure record template.
Factory loop Proof Run.

## 23. First Intake Example

```yaml
request_id: REQ-EXCEL-PDF-001
request_title: Excel to PDF Converter
requester: Josh Evans
plain_language_request: Convert Excel files into PDF files with basic layout options.
expected_output: runnable CLI converter
acceptable_80_percent_solution: >
  Given a one-sheet .xlsx, produce a readable PDF at the given output path,
  with the source file unmodified.
output_type:
  category: utility
  delivery_format: CLI tool
  must_run_on: local machine
language_lanes:
  preferred: [python]
size_estimate: S
inputs:
  files: [.xlsx]
  user_inputs: [source path, output path]
outputs:
  files: [.pdf]
hardware_store:
  required_search_terms:
    [file converter, spreadsheet reader, PDF writer, CLI wrapper, path validation]
contracts:
  required_behaviors:
    - accepts input path
    - validates file exists
    - writes PDF output
    - reports a useful error on an invalid file
  invariants:
    - source file is not modified
    - output path is explicit
  proof_run: convert the sample workbook and diff the source hash before and after
delivery:
  output_location: dist/
  outside_user_possible: true
```

## 24. Immediate Work Orders

Both orders below meet §13 in full. Neither builds the converter.

```
WORK ORDER — CF-INTAKE-001
Anchor: FACTORY-S3 (intake becomes real)
Bench: Codex
Goal: Create the Intake Form v1 YAML schema and one validated example intake.
Invariant: A request captured in this schema contains enough information to
  generate a buildable Blueprint without further questions.
Scope: intake schema; the REQ-EXCEL-PDF-001 example; a schema validation test;
  one documentation note.
Non-goals: building the converter; any UI; supporting every language;
  automatic Blueprint generation.
Repository: codeforge
File allowlist: schemas/intake/**, examples/intake/**, tests/schemas/**,
  docs/intake.md
Bench claim: required before edit
Language: python (schema + test), yaml (artifacts)
Hardware Store search: schema validator, typed settings, YAML validation,
  CLI input Parts
Contract tests: the example validates; a malformed example fails with a
  field-level message; a missing required-core field fails
Expected Break Test: remove one required-core field, validation must redden
Definition of done: validation test passes on the example and reddens on both
  negative cases, run this session
Proof Run: <the schema validation command>, output captured
Rollback: revert the commit; no runtime surface touched
Approval gates: none (reversible, execute on sight)
Size: S
Reusable Part signals: record reimplemented / recurrence / generalizable /
  friction, or "none observed"
```

```
WORK ORDER — CF-BLUEPRINT-001
Anchor: FACTORY-S3 (intake becomes real)
Bench: Claude Code
Goal: Design Blueprint v1 schema from the Intake Form and Workshop canon, plus the
  two agent handoff templates.
Invariant: A Blueprint generated from an intake contains enough information to
  assign Codex and Claude Code Work Orders with no vague prompts and no missing
  §13 fields.
Scope: Blueprint schema including blueprint_version and the regeneration ownership
  split; Work Order mapping rules; Codex handoff template; Claude Code handoff
  template; one Blueprint draft generated from REQ-EXCEL-PDF-001.
Non-goals: implementing the converter; changing runtime behavior; new doctrine;
  any UI.
Repository: codeforge
File allowlist: schemas/blueprint/**, templates/handoff/**, examples/blueprint/**,
  docs/blueprint.md
Bench claim: required before edit
Language: yaml (schema + templates), markdown (docs)
Hardware Store search: Blueprint, Work Order, Bench Report, typed settings,
  validation Parts
Contract tests: the draft Blueprint contains language lanes, tool utilization,
  Store search terms, contracts, Work Orders each carrying every §13 field, and a
  Proof Run; a draft missing any §13 field fails validation
Expected Break Test: delete the anchor from a generated Work Order, validation
  must redden
Definition of done: the generated draft passes validation and the Break Test
  reddens, run this session
Proof Run: <the Blueprint validation command>, output captured
Rollback: revert the commit
Approval gates: Principal Engineer reviews the schema before it drives real orders
Size: M
Reusable Part signals: record reimplemented / recurrence / generalizable /
  friction, or "none observed"
```

## 25. Road Summary

The factory is the vision.
The Intake Form is the front door.
The Blueprint is the configured build plan, versioned, with clear ownership.
The Hardware Store supplies proven Parts.
The Language Lane registry makes omni-code real and checkable.
The Tool Utilization registry makes tools explicit.
Codex and Claude Code receive Work Orders, never vague prompts.
The Proof Run is written before the build it judges.
The Optimization Pass improves working outputs with measurement.
Failures are recorded, not abandoned.
The execute posture keeps the Workshop moving after baseline.

The loop:

INTAKE, CONFIGURE, BUILD, PROVE, DELIVER, HARVEST, OPTIMIZE, CONTINUE.

The shortest version:

Any language. Any product. One intake. One Blueprint. Right tools. Right Parts.
Clear Work Orders. Prewritten proof. Working output. Harvest Parts. Keep building.
