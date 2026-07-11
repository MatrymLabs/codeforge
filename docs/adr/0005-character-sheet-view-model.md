# ADR-0005: Render character sheets through a view model

**Status:** accepted (scopes the first character-system batch; the wider character model is still open)

## Context

CodeForge is growing its first playable JRPG-style game. The character **score sheet** is,
in the design doctrine, "the readable surface of the character system" - identity, level,
jobs, attributes, derived stats, equipment, resistances, all in one fixed-width panel.

The existing sheet (`jobs.render_sheet`, the `score` verb) reads straight off the live
`Session`. That is fine while a character is four fields, but the JRPG sheet shows twenty
information groups, several of them optional (no secondary job, absent MP, an unknown
resistance) and some not yet modeled in persistence at all (separate job level, per-job TP).
Binding a rich renderer directly to database fields would couple presentation to a schema
that is still changing, and make the sheet impossible to test without a live world.

## Decision

The score sheet is rendered from a **view model, never from the database or the Session**.

- `parts/score_sheet.py` defines `CharacterSheet` (a plain, frozen view model) and
  `render_score_sheet(sheet, display_mode)`. The renderer consumes only the view model.
- The view model is populated from any source through `sheet_from_mapping` - a JSON fixture
  today, a live-character projection later - so the sheet's input shape is decoupled from
  its origin.
- The renderer is **presentation only**: it computes no formulas and mutates nothing. Long
  text is clipped to its column rather than breaking the frame; optional data is honestly
  optional (missing MP omits the line, a missing resistance reads `?`).
- Format is pinned by **one golden snapshot** (`tests/fixtures/characters/matrym_engineer_*`);
  content and edge cases are pinned by focused field tests. Accidental spacing regressions
  turn the suite red without making every test depend on exact spacing.

## Consequences

- **Testable and stable:** the sheet renders from a fixture with no server or database, and
  the schema underneath can change without touching the renderer.
- **Reusable:** the same renderer serves a personnel dashboard, a training transcript, or a
  maintenance status board (filed in the Hardware Store as `score-sheet-renderer`).
- **A seam for the open decisions:** the attribute set, the separation of player and job
  level in persistence, the meaning of TP, and the derived-stat formulas are all still open
  (see the character-system junctures). The view model lets the sheet exist and be proven
  now, while those decisions are made deliberately, without a renderer rewrite each time.

## Alternatives weighed

- **Render from the Session/DB directly (status quo `render_sheet`).** Simple for a tiny
  character, but couples a rich, optional-heavy sheet to a mutating schema and cannot be
  tested without a live world. Kept for the current small `score` verb; not extended.
