# CodeForge Theme Alignment Report

*A thematic audit of every named subsystem against the CodeForge vision: a software engineering
workshop, manufacturing system, research laboratory, and world-building platform. This is a review
and a set of proposals - not a rename campaign. Persisted identifiers (verbs, labels, CARD names,
catalog ids, seed keys, DB columns) are frozen; every recommendation here is gated, and most are
"keep the name" because CodeForge's naming is already strongly forge-voiced and coherent. Module-
level thematic names are covered in the [V3 vision review](v3_vision_review.md); this report is at
the subsystem and branding level. The governing rules are in the [Naming Standard](naming_standard.md).*

## The vision, as one line

Ideas become Blueprints. Blueprints become Parts. Parts become Systems. Systems become Products.
Products become Worlds. Worlds become reusable Seeds. Knowledge becomes engineering assets.
Engineering assets become Hardware Store components. Every name should reinforce that chain.

## Verdict summary

Of ~20 named subsystems, **17 keep their names** (already engineering-clear and on-theme), **1 gets a
recommended engineering alias** (Rituals), and **the rest are cross-referenced** to the module-level
review. The workshop already feels like one shop; the audit protects that, it does not remake it.

## The audit

Fields per the brief: Current Name, Recommended Name, Purpose, Reason for Change, Branding Impact,
Engineering Impact, Migration Difficulty, Recommended Priority.

| Current | Recommended | Purpose | Reason | Branding | Engineering | Migration | Priority |
|---------|-------------|---------|--------|----------|-------------|-----------|----------|
| **ARC** | keep | Assurance/Readiness/Control review umbrella | Own acronym, engineering-meaningful, foundational | Strong, ownable | Clear once expanded | n/a | - |
| **AURA** | keep | Adaptive Unified Reasoning Assistant | Own acronym, foundational; not a franchise ref | Strong, ownable | Clear once expanded | n/a | - |
| **Hardware Store** | keep | Catalog of reusable engineering parts | The exemplar: fabrication metaphor, instantly understood | Signature | Perfect (parts + cards) | n/a | - |
| **Blueprints** | keep | A plan as data before code | Core engineering term AND forge-voiced | Signature | Perfect | n/a | - |
| **Cards** | keep (say "part card") | One catalog entry for a part | Index-card metaphor fits a parts catalog | Good | Clear | n/a | - |
| **Gates** | keep | A checkpoint that must pass (QualityGate, VeritasGate) | "Quality gate" is industry-standard AND workshop-apt | Good | Clear | n/a | - |
| **Rituals** | **Checklists / Procedures** | Ordered startup/shutdown/integrity routines | "Ritual" is ceremony, not engineering; a checklist is the QA/technical-order voice Josh already uses | Neutral-to-better | Clearer intent | **Medium** (verb/target/doc references, not a data contract) | **P2** |
| **Doc** | keep ("Docs") | Documentation | Plain and clear | Fine | Clear | n/a | - |
| **Libraries** | keep | Research Library, Guidance Library | "Library" is universally understood | Good | Clear | n/a | - |
| **Research** | keep | Research translation into assets | Plain, on-theme (the lab) | Fine | Clear | n/a | - |
| **Diagnostics** | keep | System inspection and health | Engineering-standard | Good | Clear | n/a | - |
| **Testing** | keep | The test twins, gates, evidence | Plain and clear | Fine | Clear | n/a | - |
| **Patch Management** | keep | Dependency/CVE patch tracking | Industry-standard term | Good | Clear | n/a | - |
| **Change Management** | keep | The gated change lifecycle | Industry-standard term | Good | Clear | n/a | - |
| **Learning Engine** | keep (Classroom + Learning Records) | Teach + capture engineering lessons | Descriptive; the Classroom is the world-facing room | Good | Clear | n/a | - |
| **Pattern Detection** | keep (**Harvest Lens**) | Detect reusable-pattern candidates | Already a strong CodeForge name: "harvest patterns," "Lens" = a diagnostics reader | Signature | Clear | n/a | - |
| **MUD Engine** | keep (subtitle "the Forge core / tick") | The pure-function engine tick | Descriptive; document the forge-voice meaning, do not rename the contract | Good | Clear | n/a | - |
| **Seed Architecture** | keep | A world packaged as a reusable Seed | "Seed" is a core spiral-motif metaphor (seeds become systems) | Signature | Clear | n/a | - |
| **Repository Organization** | keep | The flat-parts, registry-domain layout | Recorded in ADR-0007; not a naming problem | Fine | Clear | n/a | - |
| **GitHub Presentation** | keep (the "storefront") | The public portfolio face | Plain; the shop-window metaphor is already used | Good | Clear | n/a | - |

## The one recommendation, expanded

**Rituals -> Checklists (or Procedures).** "Ritual" reads as ceremony; every other CodeForge name
reads as a tool. Josh's own voice is checklists, technical orders, and readiness rituals from a QA and
military-systems background - so **Checklist** is both more engineering-clear and *more* his identity,
not less. This is a display/terminology change (docs, a Makefile target name, prose), **not** a
frozen-identifier rename, so migration is medium and reversible. Priority P2: do it when the docs are
next touched, not as an urgent campaign. (If kept, "Ritual" should at least carry the subtitle
"readiness checklist" in the glossary.)

## What this audit deliberately does NOT do

- **No frozen-identifier renames.** Verbs (`store`, `arc`, `harvest`, `learnings`, ...), catalog ids,
  CARD docstring names, seed keys, and DB columns stay. Renaming them breaks save files, seeds,
  migrations, tests, and the public interface - a high-risk juncture reserved for Josh.
- **No re-litigating module names.** `veritas`, `frameup`, `hubble`, `foundry`, `cast` already have
  recommended engineering aliases in the V3 vision review; this report points there.
- **No new subsystems.** This is a naming audit, not a feature.

## Priority ledger

- **P2 (when touched):** adopt "Checklist" terminology for Rituals in docs; add ARC/AURA and the
  subsystem names to the naming glossary with their engineering meaning.
- **P3 (opportunistic):** add engineering subtitles to thematic module names per the V3 review as
  each file is next edited.
- **Reserved for Josh (high risk):** any actual rename of a frozen identifier.

The result: one coherent workshop whose names already reinforce the vision, protected by a written
standard rather than churned by a rename pass.
