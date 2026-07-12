# CodeForge Naming Standard

*The rules every future name follows - code, documentation, commands, subsystems, repositories, and
Hardware Store components - so the whole platform speaks one language. This is the governing standard;
the [naming glossary](naming_glossary.md) is the living vocabulary and the
[theme alignment report](theme_alignment_report.md) is the audit that produced it.*

## The one test

Before you name anything, ask: **does this name reinforce the CodeForge vision** - a workshop,
manufacturing system, research lab, and world-building platform? A name passes when it is
immediately understandable, memorable, sounds like an engineering tool, scales as CodeForge grows,
and another engineer would intuitively grasp its purpose.

## Rule 1 - Engineering purpose first

A name must communicate what the thing does. Prefer the engineering noun (`validator`, `repository`,
`circuit_breaker`, `stream_framer`) over decoration. Banish generic names - `manager`, `handler`,
`processor`, `data`, `item`, `thing`, `result` - in favor of something with a face and a purpose.

## Rule 2 - The forge voice lives on the surface, not in the contract

Thematic names (the forge/detective/tower/spiral voice) belong on the **world-facing surface**: room
names, verbs, subsystem identities. The **data contract stays literal**: `lowercase_snake_case`
labels, YAML seed keys, DB columns, JSON record keys, catalog ids, and CARD docstring names are
plain and permanent. The metaphor lives in the code and the world; never in the thing another system
persists, loads, or tests against.

Reach for the signature vocabulary when naming new surfaces: **Forge, Spark, Core, Kiln, Seed,
Spiral, Gate, Echo, Signal, Trace, CaseFile, Archive, Floor, Skill, Quest, Lens, Keystone, Relic**;
verbs **ignite, forge, trace, deduce, unlock, ascend, attune, calibrate, resolve, harvest**. A
diagnostics reader is a `Lens`; a validated installer is a `Gate`.

## Rule 3 - Clarity outranks poetry

If a name makes the purpose unclear, it is wrong. `inspect_passkey` is good; `attune_the_arcane_ward`
is not. Whenever a name is primarily thematic, it must carry a one-line **engineering subtitle** in
the glossary and its docstring, so a stranger reads the purpose in seconds (e.g. `veritas` -
consistency-audit gate; `Harvest Lens` - reusable-pattern detector).

## Rule 4 - Frozen identifiers are never renamed

These are permanent; changing one breaks save files, seeds, migrations, tests, or the public
interface, and is a high-risk juncture reserved for Josh:

- CLI verb strings (`serve`, `play`, `grant`, `migrate`, `passwd`) and in-world verbs (`store`,
  `arc`, `harvest`, `learnings`, ...)
- `lowercase_snake_case` labels (room / item / npc / job keys), YAML seed keys
- database column names, JSON/persistence record keys, account/character handle formats
- CARD docstring names, catalog part ids, registry designations
- `__init__`, `__str__`, dunder methods, pytest test function names, third-party API symbols

Improve these only by adding a display alias or a subtitle, never by renaming the contract.

## Rule 5 - The layered identity model

For catalogued things (Hardware Store parts), separate four responsibilities so classification can
evolve without renaming (see the catalog V3 redesign):

- **Identity** (permanent): the slug id (`token-bucket`) - never changes.
- **Catalog address** (re-classifiable): a derived filing aid (`05.003`) - labels are identity,
  numbers are filing aids.
- **Display designation** (presentation): readable context, computed.
- **Metadata tags** (grows over time): many classifications, never encoded into the id.

## Rule 6 - Build CodeForge's identity, not a franchise's

The workshop may *feel* like a fabrication lab, but names reference **CodeForge's own world**, never
an external franchise or pop-culture property. The vibe is aspiration; the vocabulary is ours.

## Rule 7 - Acronyms earn their letters

A named acronym subsystem (ARC = Assurance, Readiness, Control; AURA = Adaptive Unified Reasoning
Assistant) must expand to something engineering-meaningful and be spelled out on first use in any
doc. No acronym that does not stand for a real, useful phrase.

## Rule 8 - Consistency across every surface

The same concept carries the same name everywhere: terminology, documentation, folder names,
commands, developer workflows, architecture diagrams, Hardware Store cards, GitHub presentation, and
future public branding. When a concept is renamed at the display layer, update all of these in the
same change. A new name is not adopted until the glossary records it.

## Applying the standard to new work

- **A new part:** engineering-clear slug id (Rule 1, 4), a `CARD:` line stating its purpose, a
  glossary entry if the surface name is thematic (Rule 3), and the layered identity if catalogued
  (Rule 5).
- **A new verb / room:** forge-voiced is welcome (Rule 2), but the help line states the engineering
  purpose (Rule 3); the verb string is then frozen (Rule 4).
- **A new subsystem:** it must fit the vision chain (ideas -> blueprints -> parts -> systems ->
  products -> worlds -> seeds); if the name needs a franchise to explain it, rename it (Rule 6).

The end state: one coherent engineering platform with its own language, where every name reinforces
the CodeForge vision and every subsystem feels like it belongs in the same workshop.
