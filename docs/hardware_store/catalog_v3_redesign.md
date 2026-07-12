# Hardware Store Catalog V3 - Redesign Report

*A Version 3 redesign of the Hardware Store as CodeForge's engineering knowledge base and
manufacturing inventory. This is the analysis and the doctrine; the safe foundation ships alongside
it (`catalog/domains.yaml` + `parts/store_index.py`). Every renumbering, schema change, or frozen-
identifier rename it discusses is a proposal gated on Josh's approval.*

## 1. Executive Summary

The catalog is healthy (40 parts, each with a core, adapters, tests, provenance) but its
classification is ad hoc: 31 distinct `category` strings, inconsistently spelled (`rate-limiting` vs
`change_management`), with no stable engineering taxonomy and no addressing scheme. V3 fixes the
*organization* without disturbing the *parts*. The key realization: the four-layer identity model the
prompt asks for already matches CodeForge's own doctrine - **"labels are identity, numbers are filing
aids"** (`parts/catalog.py`). So the slug `id` is the permanent identity, a catalog address is a
derived filing aid, and neither the parts nor their tests need to move. The foundation (a 19-domain
taxonomy and a derive-don't-store addressing + search tool) ships with this report.

## 2. Hardware Store Vision V3

The Hardware Store is the engineering memory of CodeForge: proven mechanisms, cataloged by purpose,
refined, and reused to build both the playable world and professional software. Nothing enters
because it was coded; a part earns its place through research, implementation, testing,
documentation, demonstration, and reuse. It should read like a professional parts catalog, not a
language reference.

## 3. Recommended Catalog Architecture

Four separated responsibilities (the prompt's layered model, mapped to what exists):

| Layer | V3 role | In CodeForge |
|-------|---------|--------------|
| **Identity** (permanent) | never changes | the slug `id` (`token-bucket`) - already frozen |
| **Catalog Address** (classification) | where it belongs, may evolve | `domain.ordinal` (`05.003`) - **derived**, shipped |
| **Display Designation** | readable context | `PRT-<DOMAIN>-<address>` (proposed, computed) |
| **Metadata Tags** | many classifications | the existing `tags` list, grown over time |

Identity never changes; classification, presentation, and metadata evolve independently. The address
is a *filing aid* recomputed from the taxonomy, so re-classifying a part never renames it.

## 4. Recommended Naming Standard

Part names state engineering purpose (`Workflow Engine`, `Circuit Breaker`) - already the norm.
Slugs stay `lowercase-kebab`, permanent. Domain names are Title Case nouns. No thematic-only names in
the catalog (the theme lives in the game adapter's verb, not the card).

## 5. Recommended Addressing Scheme

`Domain.Component` today (`05.003`), extensible to `Domain.System.Component` (`05.01.003`) when a
domain grows sub-systems - **without renumbering existing parts**, because the ordinal is a display
filing aid, not identity. Unmapped parts file under `00` (visibly, never hidden). Shipped in
`parts/store_index.py::addressed`.

## 6. Recommended Metadata Model

Keep the identifier tiny; everything else is metadata. Tags allow multiple classifications
(`workflow`, `reusable`, `approval`, `state-machine`). Search reads metadata, not the ID. The ID
encodes nothing that metadata should own (the prompt's rule): domain lives in the taxonomy, maturity
in its field, provenance in `source_status`/`influence`.

## 7. Recommended Card Template

The full V3 card (superset of today's ~14 fields), migrated incrementally as additive optional
fields (the loader already ignores unknown keys, so this never breaks): **part_id, catalog_address,
designation, name, purpose, problem_solved, domain, subsystem, interfaces, inputs, outputs,
dependencies, configuration, game_uses, practical_uses, related_parts, testing, documentation,
blueprint_refs, research_refs, evidence, performance_notes, security_notes, limitations, maturity,
owner, version, revision_history, status, tags.** Ship the template; backfill per-part on touch, not
in one risky bulk edit.

## 8. Recommended Top-Level Domains

Nineteen, covering every current category with room to grow (shipped in `catalog/domains.yaml`):
Validation, State, Workflow, Events, Resilience, Persistence, **Caching** (reserved - the Harvest
Lens already found this gap), Observability, Testing, Security, Configuration, Parsing, Presentation,
Plugins, AI, Change, Learning, Search, World Systems. Expand only when a category needs a home.

## 9. Recommended Search Model

Multi-field search over id, name, purpose, category, maturity, tags, and domain (shipped in
`store_index.search`; verb `store find <query>`). Extensible to filter by dependencies, inputs,
outputs, status, blueprint, and research as those fields are populated by the V3 card template.

## 10. Recommended Repository Structure

No moves. The catalog artifacts already have homes and stay: cards in `catalog/parts.yaml`, the
taxonomy in `catalog/domains.yaml`, manifests in `docs/hardware/`, pattern docs in
`docs/hardware_store/patterns/`, tests as twins, benchmarks in `benchmarks/`, evidence in
`reports/` (generated). Discoverability comes from the domain index, not from folders.

## 11. Recommended Pattern Capture Workflow

Already built: the **Harvest Lens** (`parts/harvest_lens.py`, the `harvest` verb) scans source for
reusable-pattern signals not yet stocked and drafts candidate cards. Nothing is stocked
automatically; every candidate needs evidence (core + two adapters + tests + provenance). This closes
the loop the prompt asks for: as CodeForge writes code, the store proposes what it could preserve.

## 12. Recommended Promotion Workflow

Adopt the richer V3 maturity ladder, mapped from today's enum so nothing regresses:
`candidate -> prototype -> demonstrated -> tested -> stable -> deprecated -> archived`. Interim
mapping: current `prototype`->prototype, `beta`->demonstrated/tested, `shipped`->stable, plus new
`deprecated`/`archived`. Promotion requires evidence (the loop trace + tests + manifest). Changing the
maturity enum is a schema change - **gated on Josh** (section 23).

## 13. Recommended Blueprint Integration

Many-to-many: each Blueprint lists the Hardware Store parts it uses; each card lists the Blueprints
that use it (`blueprint_refs`). ARC's blueprint (`blueprints/arc`) is the model. Wire as additive card
fields; a future check verifies the links resolve both ways.

## 14. Recommended Research Integration

Every card records inspiration honestly (`influence`, plus `research_refs` in the template): the
standard, pattern, or documentation it was rebuilt from. **No card claims originality for a renamed
pattern** - record inspiration, implement independently (already the provenance discipline: harvested
/ independent / original, never copied).

## 15. Recommended ARC Integration

Add a **catalog-readiness dimension** to ARC: every stocked part has a passing loop trace, a manifest,
tests, and honest provenance; a card missing evidence is `watchlist`, never `stable`. ARC reads the
catalog's evidence; it never edits a card. Fits ARC's read-only, compose-existing-gates design.

## 16. Recommended AURA Integration

AURA assists over the catalog: explain a part, find the right part for a problem ("I need to fan an
event to handlers" -> `typed-event-bus`), draft a candidate card from a harvested pattern, and
translate a research finding into a card stub. AURA proposes; evidence and the loop verify; Josh
files. Behind the authenticated seam; never auto-stocks.

## 17. Recommended Migration Strategy

Additive and reversible, in this order: (1) taxonomy + addressing + search **[shipped here]**; (2)
richer card fields as optional keys, backfilled on touch; (3) blueprint/research cross-refs; (4)
maturity-ladder adoption; (5) numeric `part_id` + `designation` as computed display layers. Each step
is `make check`-gated; none renames a slug or renumbers a registry designation.

## 18. Existing Categories to Rename

None renamed in place (categories are referenced by cards). Instead, **normalized by mapping** into 19
domains, which absorbs the inconsistencies (`rate-limiting` and `resilience` both -> Resilience;
`change_management` -> Change) without editing a card. The category field becomes a sub-label under a
stable domain.

## 19. Existing Categories to Merge

Merged at the domain layer: {orchestration, control-flow, rules-engine, decision} -> **Workflow**;
{observability, diagnostics} -> **Observability**; {testing, quality, evidence} -> **Testing**;
{security, authorization} -> **Security**; {rendering, presentation, api} -> **Presentation**;
{validation, data-integrity, content-schema} -> **Validation**; {eventing, messaging} -> **Events**.

## 20. Existing Categories to Remove

None. Every category maps to a domain; none is dead. `mechanics`/`modeling` are game-specific but real
(World Systems, State) - kept, not removed.

## 21. New Categories to Create

**Caching** (domain 07) - reserved and empty, because the Harvest Lens found a `cache` pattern
recurring across ~8 sites (`loader_cache`, `load_catalog`, `load_manifest`) with no card. It is the
strongest next-harvest candidate. Others (Scheduling, Queues, Networking, Deployment) reserved for
when a part earns them.

## 22. Low-Risk Migration Plan

1. **[shipped]** `catalog/domains.yaml` + `parts/store_index.py` + the `store` verb - derive
   addresses and search, zero card edits.
2. Add optional V3 card fields; backfill a part's fields only when its card is next touched.
3. Blueprint/research cross-reference fields (additive).
4. An ARC catalog-readiness dimension (read-only).

Each additive, reversible, `make check`-gated. No frozen identifier moves.

## 23. High-Risk Decisions Requiring Approval

Reserved for Josh, do not start without go: changing the **maturity enum**
(`prototype/beta/shipped` -> the seven-stage ladder) - a schema change touching every card and the
loader; assigning **numeric `part_id`s** as a new required field; **demoting the Borg registry
designation** from primary to legacy (it is referenced by manifests and tests); any **card
renumbering or slug rename** (frozen); making V3 card fields **required** rather than optional.

## 24. Final Version 3 Hardware Store Doctrine

The Hardware Store is the manufacturing inventory of CodeForge: proven engineering mechanisms,
cataloged by purpose, each with a permanent identity, a re-classifiable address, rich metadata, and
evidence. A part earns its place; nothing is stocked because it was coded. Identity never changes;
classification, presentation, and metadata evolve. Every card teaches, tests, documents, proves
provenance honestly, and strengthens both the playable world and professional software. The store
grows by harvesting proven patterns (the Harvest Lens proposes; evidence and the loop verify; Josh
files), and it is searchable, addressable, and understandable - the engineering knowledge base where
CodeForge remembers what it has learned to build.
