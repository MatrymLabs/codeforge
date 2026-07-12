# CodeForge Continuous Improvement Doctrine

*How CodeForge improves itself while staying under human control. This is the operating loop; most of
its stations already exist as parts, and this doc names them as one system. It complements
`optimization_ethos.md` (why we optimize) and `human_keel_doctrine.md` (who decides).*

## The loop

```
Write -> Test -> Analyze -> Refactor -> Compare -> Learn -> Version -> Catalog -> Reuse
```

Each station maps to something real in the repo:

| Station | What it means | Where it lives |
|---------|---------------|----------------|
| Write | build the smallest correct version | the part + its tick verb |
| Test | prove it, incl. property + hostile cases | the test twin, `make check` |
| Analyze | multiple evidence sources, not just green tests | ruff, mypy, coverage, ARC, `frameup` |
| Refactor | improve only where evidence supports | the optimization ladder (ethos) |
| Compare | side-by-side, never replace on a whim | an improvement proposal (below) |
| Learn | capture why it changed | a **Learning Record** (`learnings` verb) |
| Version | never overwrite; v2, preserve history | the registry `-R` revision + `superseded_by` |
| Catalog | stock a proven, reusable part | `catalog/parts.yaml`, `make loop` |
| Reuse | find it before building again | `store find`, the **Harvest Lens** |

## Search before you write (station zero)

Before any new code: search the repo for an existing implementation, search the Hardware Store
(`store find <query>`), and search for duplicate or similar logic (the `harvest` verb surfaces
recurring patterns). Decide whether to reuse, extend, version, or (only if nothing fits) create. This
doc's own build followed it: the search found the Harvest Lens (pattern capture) and the record
artifacts already existed, so only the Learning Record was genuinely missing.

## Pattern capture (do not refactor on sight)

When a recurring pattern appears (repeated validation, state transitions, command routing, retry,
parsing, adapters, report generation, event handling, health checks, utilities, workflow), **do not
immediately refactor**. Instead: document it, compare it against existing cards, and decide -
reuse / extend / become v2 / become a new card. The **Harvest Lens** (`parts/harvest_lens.py`)
automates the discovery; a human makes the decision with evidence.

## Improvement proposals

An improvement is proposed, not imposed. Every proposal states: current implementation, observed
weakness, evidence, proposed improvement, benefits, tradeoffs, compatibility impact, testing
requirements, migration requirements, rollback strategy, and a recommended semantic version. If a
superior design is found, produce a **side-by-side comparison** (correctness, readability,
maintainability, performance, security, complexity, dependencies, compatibility, reuse, learning
value, developer experience) - never a silent replacement. Recommend an improvement only when
measurable evidence supports it; difference is not improvement.

## Never overwrite a part

A Hardware Store part is never overwritten. An improved implementation becomes a **new version**
(the registry designation carries an `-R` revision, and `superseded_by` links the old to the new),
preserving full history. Promoting or versioning a part is a human decision (below).

## Learning Records

Every meaningful improvement leaves a **Learning Record** (`data/learning_records/*.json`, the
`learnings` verb): what changed, why, the evidence, the tradeoffs accepted, future reuse
opportunities, and the concepts Josh should understand. It is validated data, git-diffable, browsable
- institutional memory, not a chat log. Distinct from a keel record (ownership), a pioneer experiment
(a bold trial), and a postmortem (an incident).

## Evidence to track per change

Tests passed, complexity changes, performance changes, duplicate reduction, maintainability,
dependency count, documentation completeness, Hardware Store reuse count, and new reusable
abstractions discovered. Honest labels only (verified / likely / neutral / regression / inconclusive
/ rejected), per the optimization ethos.

## Controlled autonomy

**Safe to do automatically:** formatting, lint fixes, documentation updates, import cleanup,
deterministic code generation, and small tested vertical slices (branch -> `make check` -> PR).

**Requires Josh's approval:** architectural redesign, dependency replacement, breaking API changes,
migrations, persistence changes, security-model changes, **Hardware Store promotions**, and **major
version upgrades**. AURA proposes, the system measures, the tests verify, Josh decides.

## The Continuous Improvement Report

At the end of a task, produce a report: work performed, repository impact, tests executed, quality
findings, optimization opportunities, duplicate patterns discovered, components reused, new card
candidates, components needing a new version, Learning Records generated, documentation updates,
metrics, risks, decisions requiring Josh's approval, and the recommended next iteration. It is the
task's after-action review - evidence that the loop ran.
