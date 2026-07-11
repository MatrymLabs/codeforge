# Human Keel Doctrine

*The Ship of Theseus principle for AI-assisted engineering.* CodeForge is built with
extensive AI assistance. That does not mean the human contribution disappears. The
governing question:

> If AI gradually replaces every visible plank of the code, what makes CodeForge still
> Josh's work?

The answer is not file ownership. It is that the **keel stays human**: purpose,
architecture, constraints, judgment, tradeoffs, acceptance criteria, risk decisions,
testing standards, interpretation, learning, approval, and responsibility. AI may build
the planks. Josh keeps the keel. AI may help rebuild the ship. Josh decides where it sails.

This doctrine is the durable source. Its one machine-enforced rule is wired into the
**Career Evidence Board** (see "Wired into the board" below): the ownership axis, graded
by the KeelGate.

## Keel, Frame, Planks

- **Keel (must remain human):** mission, values, purpose, authorship intent,
  responsibility, acceptance criteria, architectural authority, ethical judgment, product
  direction.
- **Frame (shared human and AI work):** architecture, interfaces, module boundaries, design
  patterns, data flow, workflows, testing strategy, documentation structure. AI may propose
  the frame; Josh must understand and approve it.
- **Planks (replaceable implementation):** functions, classes, adapters, renderers,
  utilities, tests, scripts, configuration, documentation wording. These may be replaced
  repeatedly without erasing authorship, as long as the keel and design continuity remain
  human-controlled.

## The Ownership Gate (levels 0 to 5)

A feature is not fully human-owned merely because it runs. Ownership is a second axis,
orthogonal to whether an artifact exists:

| Level | Name | Meaning | Status |
|---|---|---|---|
| 0 | `ai_output` | AI produced it; Josh has not yet verified or understood it | not_owned |
| 1 | `reviewed` | Josh inspected it and understands its purpose | partial_ownership |
| 2 | `verified` | Josh ran the tests, confirmed behavior, inspected the risks | operational_ownership |
| 3 | `modified` | Josh changed the code, tests, design, or docs from understanding | strong_ownership |
| 4 | `defendable` | Josh can explain why it exists, how it works, what can fail, how it is tested, and why this design was chosen | portfolio_ready |
| 5 | `extended` | Josh can adapt the system to a new use case without blindly relying on AI | reusable_ownership |

Do not claim mastery outside the demonstrated scope. Level 4 and above is a
**portfolio-ownership claim** and must be backed by a written Human Keel Record.

## Contribution labels

Use these to clarify provenance and responsibility, not as decoration:
`human_conceived`, `human_architected`, `human_specified`, `ai_drafted`, `ai_refactored`,
`ai_debug_assisted`, `tool_generated`, `externally_inspired`, `adapted_with_license`,
`human_reviewed`, `human_modified`, `human_verified`, `human_approved`, `human_owned`.

## Human Continuity Test

Before treating AI-assisted work as part of CodeForge, Josh should be able to answer: why
does this system exist; what problem does it solve; why this design; what alternatives were
considered; what could fail; how is failure detected; how is it tested; what evidence proves
it works; what tradeoffs were accepted; what would justify replacing it later; what did Josh
personally decide; what did AI merely assist with. If these cannot be answered, ownership is
incomplete.

## Human Keel Record (template)

For each major feature or portfolio-relevant system. Do not create paperwork for trivial
changes. A record may live in an ADR, a blueprint, a decision log, a feature doc, a PR
summary, or an evidence report.

```
Feature:
Date:
System:
Josh's original intent:
Problem being solved:
Human-defined constraints:
Human-defined success criteria:
Architecture decision:
Alternatives considered:
AI contribution:
Human modification:
Tests and evidence:
What Josh learned:
Final human decision:
Known uncertainty:
Future review point:
```

## Replacement threshold

Stop and ask Josh before AI replaces a core architecture, a central domain model, a major
public interface, a persistence model, a security boundary, a networking model, a test
philosophy, a major dependency, a principal design doctrine, or a feature that carries
portfolio identity. Present: what exists, what would be replaced, why, what identity or
intent may be lost, what stays continuous, migration cost, risks, test plan, rollback plan,
recommendation. Do not replace the keel while pretending only a plank changed.

## Provenance and attribution

Study patterns freely. Copy only with permission. Attribute what influenced the work. Build
original implementations where ownership matters. Every reused or externally inspired part
records: source, license, whether code was copied or adapted or only studied, what was
independently implemented, and what attribution is required. (The Hardware Store catalog
already records `source_status`, `license`, and `influence` per part.)

## AI transparency

Document AI involvement honestly: "AI-assisted implementation," "AI-generated first draft,
human-reviewed and tested," "architecture directed by Josh," "final design approved and
owned by Josh." Avoid "built entirely by hand" when false, "mastered" when evidence is
incomplete, "fully autonomous" when human review is required. Truth strengthens the work.

## Learning protection

AI must not erase the learning opportunity. For every significant AI-assisted feature,
require at least one of: Josh explains it in plain English, traces one execution path,
modifies one behavior, writes or repairs one test, identifies one failure mode, compares two
designs, interprets one benchmark, documents one tradeoff, or teaches it through the
Classroom. The loop: Ask, Predict, Generate, Inspect, Explain, Modify, Test, Reflect. Do not
move directly from generation to acceptance.

## Wired into the board (the KeelGate)

The one machine-enforced rule lives in the Career Evidence Board (`parts/career.py`,
`data/career/career_evidence_matrix.json`). Each skill may carry an `ownership` block:

```json
"ownership": { "level": 4, "keel": "what Josh personally decided", "record": "docs/adr/..." }
```

- Ownership is a **second axis**: a skill can be `proven` (its artifact exists) yet ownership
  `undeclared` (Josh has not yet claimed or defended it). That gap is the Ship-of-Theseus
  anxiety made visible, and the board names it honestly rather than hiding it.
- **KeelGate (`career.ownership_gaps`):** a skill claiming level >= 4 (`defendable`) must
  carry a non-empty `keel` line and a `record` path that actually exists on disk. You cannot
  claim "I can defend this" without a written record backing it. The test twin pins that the
  shipped board has zero violations, so the ownership claim cannot quietly overinflate, the
  same way `unproven_claims` stops the evidence claim from overinflating.
- **Undeclared is honest, not a lie.** The machine defaults ownership to undeclared; Josh
  claims each skill as he defends it. View it with `career ownership`.

## Required Claude behavior

AI proposes; the system measures; the tests verify; **Josh decides.** For major work:
identify which decisions are human decisions, offer alternatives rather than silently
deciding, state assumptions, mark uncertain conclusions, require evidence before claiming
success, name what Josh should learn, and record the human decision. Do not erase existing
intent, replace architecture silently, hide AI involvement, confuse code generation with
ownership, or treat repository control as proof of understanding.
