# CodeForge V3 - Engineering Review Report

*A dated (2026-07-13) Version 3 review artifact, NOT the canonical vision. The canonical product
vision is [vision_resync.md](vision_resync.md); where this review's framing differs, that governs.
This re-evaluates architecture, terminology, boundaries, and philosophy against the settled vision.
It is a review and a set of proposals, not a state change.
Every rename or move it recommends is gated: persisted identifiers are frozen, and structural moves
are critical junctures reserved for Josh (see [ADR-0007](adr/0007-repository-layout.md)).*

## 1. Executive Summary

CodeForge is already substantially V3-aligned. The module layer is overwhelmingly
engineering-descriptive (`accounts`, `combat`, `health`, `validation`, `workflow`, `statemachine`,
`repository`, `retry`, `circuit_breaker`, `signal_bus`, `stream_framer`); the thematic layer lives
where it should, at the room/verb/subsystem surface ("the world is the interface"). So V3 is a
**synchronization and documentation** exercise, not a redesign. The real gaps are three: (a) some
thematic subsystem names lack a documented engineering alias, (b) the review systems want ARC as a
single umbrella (already blueprinted), and (c) there is no automation that harvests reusable patterns
as code is written. This report addresses all three; the third ships in this same change as the
**Harvest Lens**.

## 2. Vision Alignment Score

**Strong (8/10).** Engineering-first naming, evidence discipline, modularity, and the one-core-
two-adapters Hardware Store are already in place. The two points off: thematic names without
engineering aliases (a clarity tax on a new reader), and the review surface being spread across
several gates rather than one ARC verdict. Neither is a redesign; both are convergence.

## 3. Systems That Perfectly Match the New Vision

- **Hardware Store** (`catalog/`, `parts/`, the manufacturing loop) - reusable parts, provenance,
  one core + two adapters, evidence per part. This is the platform thesis, working.
- **ARC** (`parts/arc.py`) - composes existing gates into one honest readiness verdict; no new gate.
- **Registry** (`registry/`) - every module filed by domain (UM04 game, UM05 store, UM10 reports).
  This IS the logical package structure, without moving a file.
- **Evidence spine** - `test_evidence`, `qualitygate`, `integrity`, `change_ledger`, `patch_tracker`.
- **Engineering-named domain parts** - `validation`, `workflow`, `statemachine`, `repository`,
  `retry`, `circuit_breaker`, `signal_bus`, `stream_framer`, `token_bucket`, `feature_flags`.

## 4. Systems That Partially Match

- **The review gates** (`qualitygate`, `integrity`, `release_gate`, safety review, dependency review)
  are individually strong but not yet unified. ARC's remaining slices close this.
- **Blueprint subsystem** (`blueprint`, `blueprint_ai`, `blueprint_render`) - cohesive, but the
  "author -> validate -> render" pipeline is not documented as one named flow.
- **Thematic subsystems** (below) - correct behavior, under-documented engineering meaning.

## 5. Systems That No Longer Fit

**None found for removal.** The integrity and Veritas audits keep dead weight from accumulating; no
orphan subsystem surfaced. Two items are *misfiled by name*, not obsolete (see renames): `frameup`
and `hubble` read as pure theme with no engineering signpost.

## 6. Recommended Renames

Persisted identifiers (labels, CLI verbs, DB columns, CARD names, seed keys) are **frozen** - none of
these are actual renames. These are **documented engineering aliases** (the name stays; the glossary
and docstring gain the engineering meaning), except where a symbol is purely internal.

| Thematic name | What it is | Engineering alias (document, don't rename) |
|---|---|---|
| `veritas` / VeritasGate | claims-match-reality audit | **consistency-audit gate** |
| `frameup` | on-demand whole-system inspection | **system inspector / self-report** |
| `hubble` | observation/diagnosis subpackage | **diagnostics-observation** |
| `foundry` | approval-gated guarded code generation | **guarded generator** |
| `cast` | build a standalone game from a seed | **game-project exporter** |
| `spark` | server/CLI entrypoint | **entrypoint** (keep verb; alias in docs) |
| `heralds` | startup announcers | **startup banners** |
| Rituals (`startup_ritual`, `repo_integrity`) | ordered procedures | **procedures / checks** |

Rule going forward (Naming Philosophy): a new engineering subsystem gets a descriptive name first;
the thematic skin lives in the room/verb, not the module.

## 7. Recommended Architectural Moves

- **Do NOT re-package `parts/` into subfolders.** The registry domains already provide the logical
  grouping; physically moving every module would rewrite imports repo-wide for no functional gain
  (ADR-0007's declined `src/` move, same reasoning). The move is the registry view, not the folder.
- Keep the four existing subpackages (`evolution`, `hubble`, `stewardship`, `web`) - they are real
  cohesive clusters.

## 8. Recommended Consolidations

- **ARC as the single review umbrella.** Finish ARC slices 2-4 so `qualitygate`, `integrity`,
  `release_gate`, dependency, security, change, and patch report through one verdict. (Blueprinted in
  `blueprints/arc`.) This is the biggest coherence win and it removes "which gate do I run?"
- **Document the Blueprint pipeline** (author -> validate -> render) as one named flow.

## 9. Recommended Removals

None. Flag for periodic review (not removal): any doc under `docs/` that duplicates a newer doc; the
integrity ritual already reports drift, so let evidence, not opinion, drive any future cut.

## 10. Recommended New Subsystems

- **Harvest Lens** (`parts/harvest_lens.py`, shipped in this change) - scans source for reusable-
  pattern candidates not yet in the Hardware Store and drafts candidate cards. It automates the
  gap-analysis loop we have been running by hand (it is how `stream-framer` and `typed-event-bus`
  were found). *As code is written, the store learns.*
- Later: a documented **Translation Pipeline** artifact (reality -> blueprint -> part -> world) so the
  platform thesis is legible on arrival.

## 11. Updated Terminology

Adopt, in the glossary and docstrings: **entrypoint, consistency-audit, system inspector,
diagnostics-observation, guarded generator, game-project exporter, review umbrella (ARC), harvest
candidate, card, one-core-two-adapters, provenance, readiness (never certification)**. Keep AURA and
ARC as foundational, unchanged.

## 12. Updated Package Structure

No physical change. The canonical grouping is the **Registry domain**: UM04 (game systems), UM05
(Hardware Store / reusable parts), UM10 (reports / evidence / review), plus subpackages for cohesive
clusters. Document this mapping in the naming glossary so a reader navigates by domain, not by
guessing from the flat folder.

## 13. Updated Repository Structure

As recorded in ADR-0007: flat importable `parts/` + root `forge.py`, single-package flagship, `src/`
declined, future project shapes in `docs/repo_templates/`. V3 changes nothing here; it ratifies it.

## 14. Updated Documentation Organization

`docs/` has ~63 top-level files - navigable but flattening. Group (by index/nav, not by moving files
yet) into: **Vision** (this report, vision_resync, optimization_ethos, human_keel), **Architecture**
(ADRs, architecture, C4), **Hardware Store** (patterns/, hardware/), **Review/ARC**, **Rituals/
Procedures**, **Research**, **Portfolio**. The mkdocs nav is the low-risk lever.

## 15. Updated Command Philosophy

Keep the namespaced command spine (`CORE` / `ADMIN @` / `SEED`). A verb is a room's window onto a
subsystem; its name may be thematic, its help line must state the engineering purpose. New review
verbs route through `arc`. No verb-string renames (frozen public interface).

## 16. Updated Engineering Philosophy

Engineering-first, evidence-driven, research-informed, reusable, modular, maintainable, playable,
educational, architecturally intentional. Prefer systems that are **observable, composable, testable,
replaceable, extensible, documented, explainable**. AURA translates, the Forge builds, ARC verifies,
the Hardware Store preserves.

## 17. Updated Game Philosophy

The world is the interface, not decoration: every room maps to a real engineering capability
(Workshop = build, ARC Chamber = review, Hardware Store = reuse, Classroom = teach, Library =
research). Thematic immersion stays in the world; the engineering meaning is always one help line or
glossary entry away.

## 18. Updated Hardware Store Philosophy

A part earns a card only with: one clear responsibility, a framework-free core, a game adapter AND a
practical adapter sharing that core, tests (incl. a property test on the invariant), a PartManifest,
provenance (harvested / independent / original - never copied), and a loop trace. The store grows by
**harvesting proven patterns**, now assisted by the Harvest Lens.

## 19. Updated Blueprint Philosophy

A Blueprint is a plan as data before code: intent, requirements, tasks, stack, status
(draft/validated), git-diffable. Major features begin as a Blueprint (ARC did). Document the
author -> validate -> render pipeline as the canonical planning flow.

## 20. Updated AURA Responsibilities

Translation (reality <-> engineering <-> architecture <-> blueprint <-> code), explanation,
engineering guidance, architecture assistance, diagnostics, research synthesis, teaching. AURA
proposes; the system measures; the tests verify; Josh decides. Behind an authenticated seam; never on
a gameplay transport; CI runs with no API key.

## 21. Updated ARC Responsibilities

Assurance, Readiness, Control: engineering review, evidence, readiness, quality, documentation
verification, testing verification, release readiness, dependency review, security review, patch and
change management - composed into one honest `ready | watchlist | blocked` verdict that reads filed
evidence and never invents it. Readiness, never certification. Finish slices 2-4 to make "every
change flows through ARC" literal.

## 22. Migration Roadmap

1. **Docs (this change):** file this report; add the Harvest Lens; expand the naming glossary with
   engineering aliases and the registry-domain map.
2. **ARC slices 2-4:** wire real gate sources, the ARC Chamber room, then the change-ledger link.
3. **mkdocs nav regrouping:** organize docs by the section map in section 14 (no file moves).
4. **Blueprint pipeline doc:** name the author -> validate -> render flow.

## 23. Low-Risk Migration Order

Glossary aliases and the docs report (pure additive) -> Harvest Lens (new part, isolated, tested) ->
mkdocs nav regrouping (no file moves) -> ARC slice 2 (read-only gate wiring). Each is reversible and
gated by `make check`.

## 24. High-Risk Architectural Decisions Requiring Approval

Reserved for Josh, do not start without go: any actual **rename of a frozen identifier** (labels,
verbs, DB columns, CARD names, seed keys); any **physical re-packaging** of `parts/`; the **ARC
slice-4** change-ledger link (alters the change lifecycle); any **doc deletion**; a `src/` migration
(already declined). AURA never assigns ownership; renames never trade away security or the evidence
trail.

## 25. Final Version 3 Vision Statement

CodeForge is a software manufacturing platform whose playable world is its interface. Reality becomes
engineering systems; systems become Blueprints; Blueprints become reusable software; reusable
software becomes both practical applications and configurable worlds. The human contributes systems
thinking, judgment, and final approval; AURA translates, the Forge builds, ARC verifies, and the
Hardware Store preserves - which now learns as it is built. Every name communicates engineering
purpose, every claim carries its evidence, and every part is observable, composable, testable,
replaceable, extensible, documented, and explainable. Not a collection of interesting ideas: a
cohesive engineering ecosystem another senior engineer can understand, extend, and trust.
