# Keel Record: Translate scholarly research into a working, tested system

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). Backs the
`adv.research.translation` ownership claim (level 4, defendable) on the Career Evidence Sign.
The keel is human even though the planks were AI-assisted: purpose, scope, and the evidence
judgments were Josh's.*

- **Skill:** Translate scholarly research into a working, tested system (`adv.research.translation`)
- **Ownership level claimed:** 4 (defendable / portfolio-ready)

## Intent
Prove that a literature survey can become a disciplined, evidence-labeled implementation, not
just a pile of consumed papers. The senior differentiator is research-to-architecture: deciding
what transfers, what is extrapolation, and what to defer, and being able to defend each call.

## Problem
A research report (Nature-Inspired Design for an AI Coding Assistant) proposes many mechanisms
at wildly different maturity levels. Naively implementing all of them would dress metaphor as
proof. The problem was to translate honestly: build what the evidence supports, label the rest,
and never let a metaphor claim to be a measurement.

## Constraints
- A metaphor is never presented as proof; every mapped mechanism carries an honest evidence label.
- Nothing is claimed to improve CodeForge until it is measured inside CodeForge.
- Governance stays human (Human Keel Doctrine): AI may propose candidates, never promote them.
- No new architecture, public interface, or persistence change without a stop-for-Josh junction.

## Success criteria
A `docs/nature_inspired/research_mapping.md` that maps each mechanism to a CodeForge translation
with an explicit label (evidence-backed / extrapolation / experimental / future / not-recommended)
and a source; a working typed genome subsystem with tests; the build composing with existing gates
rather than duplicating them.

## Decision
Build the Blueprint Evolution Lab as a staged, human-governed subsystem (`parts/evolution/`):
typed genotype to phenotype expression, a small candidate population, multi-objective fitness with
hard gates first, and a counterexample bank. Ship it in reviewable slices, each behind its own PR.

## Alternatives considered
- Implement the report end to end in one pass. Rejected: unreviewable, and it would have shipped
  low-evidence mechanisms (neuromorphic, DNA execution) as if they were justified.
- Treat the report as reading only, ship nothing. Rejected: the skill being proved is translation
  into a *tested* system, not a summary.

## AI contribution
AI-assisted implementation of the genome, candidate, fitness, and counterexample modules and their
tests; drafted the research-mapping prose; proposed the evidence labels for Josh's review.

## Human modification (the keel)
Josh set the scope (which mechanisms to build now vs defer), directed the staged-slice delivery,
approved each PR, and made the evidence-label calls (what is evidence-backed vs extrapolation vs
not-recommended). The governance boundary (AI proposes, never promotes) was a human decision.

## Tests / evidence
- `parts/evolution/` (11 modules), `tests/test_evolution_*.py` (45 tests), green on `make check`.
- `docs/nature_inspired/research_mapping.md` (the mapping, with labels and APA sources).
- Delivered across PRs #72-76 (genome/gate, bake-off, MUD surface, second subject, cards).

## What Josh learned
Translating research means grading the evidence before writing any code. The honest labels
(what transfers, what is extrapolation, what to reject) are the deliverable as much as the
modules are, and I can defend where each one landed.

## Final decision
Josh's, at the merge junction of each slice and of this record. He claims level 4 only if he can
defend the design and the evidence labels to an interviewer.

## Uncertainty / review point
Autonomous mutation operators are deliberately not built (v1 applies none). Revisit ownership if
that changes, since autonomy shifts the human-in-the-loop story this claim rests on.
