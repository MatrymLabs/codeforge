# Technology Intake and Interoperability

CodeForge prepares to adopt new frameworks, libraries, developer tools, protocols, services,
runtimes, and languages **without weakening its Python-native identity or fragmenting its
architecture**. This is the doctrine and the machine-checkable gate that enforce it.

## The principle

- **Python owns the orchestration.** Domain models, control flow, Blueprints, Hardware Store
  records, ARC evidence, and Seed assembly stay Python wherever practical.
- **Contracts define the boundaries.** External code enters through an explicit interface or adapter,
  never directly into the domain layer.
- **Adapters connect the ecosystems.** A framework's code does not leak throughout the core.
- **Tests prove compatibility.** No adoption without a testing strategy.
- **ARC controls admission.** Nothing is admitted merely because it is popular, modern, impressive,
  or requested by an AI assistant.
- **The Hardware Store preserves reusable integration knowledge.**

Other technologies may become dependencies, tools, plugins, adapters, subprocess workers, external
services, client technologies, build or render targets, optional accelerators, development-only
tools, or research references. Not every technology belongs in the core; not every one should be
rewritten in Python; not every one that *can* integrate *should*. The objective is **controlled
interoperability**.

## The onboarding office

Every incoming technology passes through, in order: candidate → identity verified → provenance
reviewed → license reviewed → capability interviewed → gap analyzed → Python assessed → architecture
placed → security screened → dependency reviewed → prototyped → tested → ARC evaluated → **human
approval** → carded → deployed → periodic review → upgrade / replace / retire / promote. No
technology bypasses onboarding merely because another project already uses it.
(`kernel.intake.ONBOARDING_STAGES`.)

## Classification

A technology holds one relationship to CodeForge (`kernel.intake.CLASSIFICATIONS`): `NATIVE_PYTHON`,
`PYTHON_PACKAGE`, `PYTHON_FRAMEWORK_EXTENSION`, `COMPILED_EXTENSION`, `SUBPROCESS_WORKER`,
`EXTERNAL_SERVICE`, `CLIENT_TECHNOLOGY`, `BUILD_TARGET`, `RENDER_TARGET`, `DEV_TOOL`,
`RESEARCH_REFERENCE`, or `REJECTED`. A `NATIVE_PYTHON`/`PYTHON_PACKAGE` row must actually be Python; a
role hosted outside the core (`SUBPROCESS_WORKER`, `EXTERNAL_SERVICE`, `CLIENT_TECHNOLOGY`,
`COMPILED_EXTENSION`, `RENDER_TARGET`) must name its boundary.

## The ten requirements

Every integration must carry all ten (`kernel.intake.REQUIRED`): **purpose, owner, contract,
security_review, license_review, compatibility, testing_strategy, failure_strategy,
upgrade_strategy, removal_strategy**. An **approved** technology missing any of them is incomplete
and the gate fails.

## The decision

The office reaches one decision (`kernel.intake.DECISIONS`): `approved`, `held`, `rejected`, or one of
the three *default-down* verdicts — `stdlib_first`, `research_only`, `integrate_later` — used when the
case is weak on need, skill, or removability. Josh retains approval authority over foundational
frameworks, new languages, runtime changes, and major dependencies.

## The gate

The intake ledger (`intake_ledger.toml`) records every onboarded technology as a
`TechnologyIntakeRecord`. `make intake` (and the test twin on `make check`) fails loud if any record
is **incomplete** (an approved technology missing a requirement) or **inconsistent** (an unknown
classification/decision, a non-Python `NATIVE_PYTHON` row, or an external role with no boundary), so
a technology cannot be adopted without a complete, consistent onboarding record. This is the sibling
of the Dependency Approval Rule (`docs/tooling_strategy.md`, `parts/dependencies.py`): that gate
justifies every *Python package*; this one onboards *any technology*.
