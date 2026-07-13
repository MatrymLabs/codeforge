# The Convergence Review

*A repeatable interdisciplinary review method for discovering blind spots by transferring
mature engineering practices across disciplines, and classifying gaps by mechanism rather
than by label.*

> Internal codename: **the Lemonade Protocol** (from the optimization ethos: do not merely
> make lemonade when you meet a problem; turn the solution into infrastructure). The
> Convergence Review is that ethos aimed outward, at the whole system, by a panel.

## What it is

The Convergence Review convenes a **board of discipline seats** to audit a system against
mature engineering **practice families**, transfer proven practices between domains, and
name the gaps a single reviewer cannot see. It is deliberately interdisciplinary: the value
is not one expert going deeper, but many disciplines each seeing a different blind spot.

It has a real professional lineage and extends it:

- **Design / Architecture Review Board** (aerospace, software): a panel reviews a system
  before it advances. The Convergence Review makes the panel *cross-disciplinary*.
- **HAZOP** (process safety): apply guide-words systematically to surface deviations no one
  reviewer would find. Here the guide-words are *disciplines* and *mechanisms*.
- **Red-teaming**: deliberately adopt an outside perspective. Here the outside perspective
  is another *profession*.

The differentiator, and it is grounded in peer-reviewed research on multidisciplinary
coding practices: **many disciplines rediscover the same practice under a different name.**
So the Convergence Review classifies findings by underlying **mechanism**, which exposes
duplication and reuse a label-based review misses.

## The governing question

Never ask *"what feature should we add?"* Ask instead:

> **"What mature engineering discipline has already solved this problem under another
> name?"**

Innovation, the literature repeatedly shows, comes less from inventing new practices than
from **transferring, integrating, and de-duplicating** mature ones. The board's job is
transfer, not invention.

## The method

1. **Seat the board.** Choose discipline seats that map to the system and to the reviewer's
   own competencies. A typical panel: records management / provenance, quality engineering
   (Lean Six Sigma / SRE), safety and systems engineering, human factors and accessibility,
   MLOps and AI governance, knowledge management and taxonomy. Add or swap seats to fit the
   target.
2. **Give each seat a lens and a beat.** Each seat reads the real system through its
   discipline and reports only what that discipline uniquely sees. Seats work independently
   so they do not converge prematurely.
3. **Grade against the practice families** (below). Where a family is absent, the seat must
   **explain why**, not just note it.
4. **Classify by mechanism** (below), not by the discipline's local vocabulary.
5. **Synthesize.** Collect the seats' findings, surface where they converge (a convergent
   finding across independent seats is the strongest signal), and produce the structured
   output.

## The practice-family checklist

Review every subsystem against the mature families the literature clusters into:
classification, standardization, documentation, version control, metadata, provenance,
traceability, testing, review, security, debugging, refactoring, automation, CI/CD,
experimentation, prototyping, MVP development, agile, DevOps, MLOps, low-code,
observability, logging, human factors, accessibility, governance. An absent family is a
finding; explain the absence.

## The mechanism lens

Behind the many labels sit a few recurring mechanisms. Classifying by these exposes the
"same practice, different outfit" duplication:

- **Judgment standardization** (rubrics, codebooks, checklists, scorecards).
- **Traceability** (version control, provenance, metadata, audit trails).
- **Exploration under uncertainty** (prototyping, MVP, experiments, spikes).
- **Quality gating** (validators, gates, review, tests, certification).
- **Lifecycle automation** (CI/CD, MLOps, pipelines, scheduled rituals).

Ask of each part: *which mechanism does this perform?* Parts that answer the same are kin,
even when their names and domains differ; that kinship is a reuse opportunity.

## The output

Every Convergence Review produces a structured report:

1. Blind spots. 2. Missing disciplines. 3. Hidden assumptions. 4. Cross-industry ideas.
5. Better existing practices. 6. Fleet-level opportunities. 7. Reusable Hardware Store
components. 8. Blueprint updates. 9. Long-term technical debt. 10. Future research
opportunities. 11. What we haven't thought of yet. 12. The next capability to build (the
"next glass of lemonade").

Findings are cited to file/artifact, ranked by fleet leverage, and honest: credit real
strengths, spend words on genuine gaps, invent nothing for its own sake.

## How it composes with the ship

- **Optimization ethos.** Every accepted finding should become infrastructure: a Hardware
  Store part, a Blueprint, a gate, a lesson. A review that only lists problems has stopped
  halfway.
- **ARC (Assurance, Readiness, Control).** The review's verified findings are assurance
  evidence; recurring gaps become new ARC dimensions or checks.
- **AURA (the intended teaching layer).** When built, AURA explains *why* each finding
  matters (exploit/failure scenario, mitigation, the reusable pattern), turning a review
  into a lesson. Until then, the "why" lives in the report prose.
- **Fleet thinking.** Every recommendation must improve CodeForge, ARC, AURA, the Hardware
  Store, Blueprints, documentation, testing, security, developer experience, future AI
  agents, future contributors, future maintainers, or future MAT Labs products. If it does
  not, generalize it until it does, or drop it.

## When to run one

On a new subsystem before it hardens; at a maturity milestone; when a system "feels done"
(the most dangerous moment); or on a cadence, to keep discovering what the current mental
model cannot yet see. The review is read-only: it finds the work, it does not do it. What
to build, and in what order, remains a human decision.

## First run

The inaugural Convergence Review (2026-07-13) is filed at
[reports/2026-07-13-lemonade-board-review.md](reports/2026-07-13-lemonade-board-review.md).
Its convergent finding: CodeForge proves the present moment well but does not retain,
relate, or measure over time, and its keystone recommendation ("the Chronicle") is designed
in [reports/2026-07-13-chronicle-design.md](reports/2026-07-13-chronicle-design.md).
