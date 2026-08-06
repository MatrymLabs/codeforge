# Aethryn Room Presentation Specification

## Authority and current evidence

The Seed Runtime owns location, exits, occupants, objects, and conditions. The current Aethryn seed
contains 77 authored rooms in `content/seeds/aethryn/rooms.yaml`; runtime installation adds the
protected Grand Library and Creator's Workshop. Current seed descriptions are zone-summary prose
and many public hubs expose named destination exits. This spec is a cleanup contract, not proof that
all sections already exist.

## Rendering order

Standard entry:

```
<AREA> — <ROOM NAME>
<short state line, only when changed or relevant>

DESCRIPTION
<one or two short paragraphs>

PRESENT
  <players/NPCs/enemies, only if present>

POINTS OF INTEREST
  <interactive objects/resources/quest hooks, only if present>

EXITS
  north — <landmark or destination>
  east  — <landmark or destination>
```

The prompt follows separately. `look` repeats the standard report. `look verbose` includes the full
description and environmental details. `exits` shows only exits; `map` shows the map projection;
`examine <noun>` resolves an object, NPC, or point of interest.

## Section policy

| Section | Entry | Changed | `look` | Verbose | Panel |
|---|---:|---:|---:|---:|---:|
| area/name | yes | yes | yes | yes | yes |
| description | short | no | yes | full | yes |
| present | if non-empty | yes | yes | yes | yes |
| objects/points | if non-empty | yes | yes | yes | yes |
| conditions | if decision-relevant | yes | yes | yes | yes |
| exits | yes | yes | yes | yes | compass + list |
| recent events | no | yes | optional | yes | event log |
| prompt hints | optional | no | no | optional | action bar |

No room entry emits a blank section. Repeated room state may be suppressed after `settings room
repeat off`, but a move always emits the room title and exits.

## Room variants

- Minimal: title, one-line description, exits.
- City: title, short atmosphere, present, points of interest, exits.
- Wilderness: title, conditions/weather only when actionable, description, resources, exits.
- Dungeon: title, light/hazard state, description, present, exits, locked/hidden notices when known.
- Creator's Workshop: title, purpose, station exits, owner-only action hints; never leaks to others.
- Combat-active: title, combat status and target first, then only actionable room changes.

## Content authoring rules

Room prose is authored as `short_description`, `long_description`, and structured `points_of_interest`;
interactive nouns do not hide in prose alone. A room can have a `display_label` on an exit without
changing its canonical direction. Builder-only notes are not rendered to players. Dynamic facts are
data fields with an explicit freshness policy, not string concatenation in the formatter.

## Required payload

`RoomPresentation` includes room id/version, area, title, short/full description, sections, visible
exits, conditions, present entities, points of interest, and available commands. Each item has a
stable id, display text, and action metadata. Hidden exits are omitted unless discovered; locked
exits are shown as `[LOCKED]` when the player can perceive the threshold.

