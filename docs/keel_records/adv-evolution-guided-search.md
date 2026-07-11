# Keel Record: Design an evaluator-guided search with human governance

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). Backs the
`adv.evolution.guided_search` ownership claim (level 4, defendable) on the Career Evidence Sign.
The load-bearing decisions, bounded search and human-final selection, were Josh's.*

- **Skill:** Design an evaluator-guided search with human governance (`adv.evolution.guided_search`)
- **Ownership level claimed:** 4 (defendable / portfolio-ready)

## Intent
Show a bounded, auditable, human-final search: evolutionary / program-synthesis concepts wired to
AI governance and human-in-the-loop selection. The hireable skill is not "run a search loop"; it
is designing one that cannot promote its own output.

## Problem
An unbounded generate-and-score loop drifts: it optimizes a proxy, spends unbounded compute, and
tempts auto-promotion of whatever "looks good." The problem was a search that stays cheap,
explainable, and human-governed, with security-sensitive decisions kept outside the loop.

## Constraints
- Hard gates (correctness / security / tests / policy) score before any weighted objective.
- Evaluators are read-only, score and explain, and have no merge authority and no self-approval.
- v1 applies no autonomous mutation; the elite baseline is never auto-replaced.
- Explicit compute / token budgets, a stopping policy, and a kill switch on every run.

## Success criteria
A bake-off that keeps 3 to 5 candidates alive, scores them hard-gates-first with every metric
visible, preserves an elite baseline, and records why each candidate won or lost, with tests
pinning the gate order and the governance boundary.

## Decision
Build `parts/evolution/bakeoff.py` + `fitness.py` + `evaluators.py`: a bounded evaluator swarm
that scores candidates, hard gates first then weighted objectives, and returns a ranked,
explained result that a human promotes (or does not). No path lets the search promote itself.

## Alternatives considered
- Single-objective fitness (one score). Rejected: hides the hard-gate-vs-preference distinction
  that keeps a security failure from being bought off by a high preference score.
- Let the top candidate auto-merge above a threshold. Rejected: violates the Human Keel Doctrine
  and the report's own governance guidance.

## AI contribution
AI-assisted implementation of the bake-off, fitness, and evaluator modules and their tests;
proposed the objective weighting and the evaluator dimensions for review.

## Human modification (the keel)
Josh decided the search is bounded and human-final: hard gates before weighted objectives, no
autonomous mutation in v1, evaluators with no merge authority, and the human kept outside the loop
for security-sensitive edits, public APIs, persistence, and destructive actions. Those are the
load-bearing calls, and they are his.

## Tests / evidence
- `parts/evolution/bakeoff.py`, `fitness.py`, `evaluators.py`; `tests/test_evolution_bakeoff.py`
  and the wider evolution suite (45 tests), green on `make check`.
- Delivered in PR #73 (the candidate bake-off) atop the typed genome (#72).

## What Josh learned
> DRAFT (Josh to confirm or replace in his own words): a guided search earns trust from its
> governance, bounded, explainable, human-final, not from a clever fitness formula.

## Final decision
Josh's, at the merge junction and of this record. Level 4 holds only if he can defend the bounded,
human-final design and its tradeoffs to an interviewer.

## Uncertainty / review point
Typed autonomous mutation operators are deferred until measurement justifies them and Josh
approves. Adding autonomy is the review point that would reopen this ownership claim.
