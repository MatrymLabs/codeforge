# Aethryn Presentation Style Guide

Status: proposed implementation contract; current behavior is evidence, not automatically the
new default. Authority remains the Seed Runtime. Text is the complete fallback; structured client
panels are projections of the same payloads.

## 1. Product grammar

Every player-facing block follows this order when relevant:

1. identity or location title;
2. one-line state or context;
3. grouped facts;
4. action or navigation affordances;
5. one-line help hint.

The character sheet is the reference language because it already demonstrates identity, a strong
header, fixed hierarchy, aligned values, compact resource bars, and grouped sections. Preserve its
hierarchy and view-model seam; extend the rules rather than cloning its border everywhere.

## 2. Profiles and widths

`standard` targets 78 visible columns, `narrow` 48, `compact` 64, `wide` 110, and `linear` is a
screen-reader-oriented one-fact-per-line profile. A renderer must measure printable width after
ANSI removal and never emit a required line wider than the profile. At widths below 48, tables
become labelled lists and two columns become sequential sections.

Default wrapping is word-boundary wrapping with continuation indentation of two spaces. A long
description is capped at 3 displayed paragraphs in a room entry; `look verbose` reveals the rest.
Never truncate a number, command, requirement, or error. Clip only optional prose and mark it with
`[more: look verbose]`.

## 3. Tokens

| Meaning | Text token | ANSI suggestion | Non-color cue |
|---|---|---|---|
| title | uppercase or title case | bold | heading position |
| normal | plain | default | none |
| important | `!` prefix only when urgent | bold | `!` |
| success | `[OK]` | green | `[OK]` |
| warning | `[WARN]` | yellow | `[WARN]` |
| error | `[ERROR]` | red | `[ERROR]` |
| locked | `[LOCKED]` | dim/yellow | literal token |
| unavailable | `[UNAVAILABLE]` | dim | literal token |
| selected | `>` | bold/cyan | `>` |
| complete | `[x]` | green | `[x]` |
| incomplete | `[ ]` | default | `[ ]` |
| resource | numeric `current/max` | optional color | numeric value |

Color is enhancement only. Unicode box drawing is optional. ASCII uses `=`, `-`, `|`, `>` and
`[ ]`; no glyph is allowed to carry unique meaning.

## 4. Borders and sections

Use a border for a deliberate report (sheet, help page, selection screen), not every room event.
Room and combat output use headings and separators without a surrounding frame by default. A frame
must fit the chosen width. Section labels are stable and sentence-like: `DESCRIPTION`, `PRESENT`,
`EXITS`, `STATUS`, `REQUIREMENTS`, `NEXT`. Empty sections are omitted unless their absence would
be confusing; explicit empty states say what to do next.

## 5. Output modes

- `compact`: only changed state, current target, actionable exits, and result.
- `standard`: normal room, combat, and character reports.
- `verbose`: full room prose, all relevant events, and explanatory hints.
- `linear`: one labelled fact per line, no columns, no decorative border.
- `debug`: owner/developer diagnostics only; never the player default.

`settings presentation <profile>` changes the profile; `settings verbosity <mode>` changes event
verbosity. A player can disable ANSI and Unicode independently.

## 6. Component rules

Progress bars always include the numeric value. Tables have a linear equivalent. Commands are shown
in backticks in documentation and as plain tokens in narrow mode. A field label ends in `:` when
the value follows on the same line. Actor and target are always named in combat results. A status
change is announced once at the point of change and may be grouped thereafter.

## 7. Structured parity

The text renderer and Master Client consume the same typed `ClientPresentationPayload`. The client
may rearrange a room into cards or a compass, but it may not invent an exit, infer an unlock, or
write authoritative state. If a panel is unavailable, the text stream remains complete.

## 8. Acceptance tests

Every formatter is tested at 48, 64, 78, and 110 columns; after ANSI stripping; with Unicode
disabled; and in `linear` mode. Snapshots are reviewed fixtures, not immutable style law. A fixture
change must state why hierarchy, content, or accessibility improved.

