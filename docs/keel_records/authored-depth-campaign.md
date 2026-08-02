# Keel Record: K4 - Authored-Depth Campaign (a real interior for every bare settlement)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). Authored world
content is the flagship game's VOICE, which is Josh's keel; AI drafts the planks (rooms, dialogue,
lore, quests) in his established canon, and Josh reviews and owns the prose. Per the doctrine, **AI
does not assign ownership**; the level-4 claim and the "what I learned" note are left for Josh.*

- **Build (this slice):** `content/seeds/aethryn/authored/caeloria_city.yaml` +
  `content/seeds/aethryn/quests/caeloria_charter.yaml` (pure data through the authored-towns
  pipeline), plus a quest-walk test twin. No engine change.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
K4 of the re-racked bench: authored depth where it is genuinely thin. A prior campaign brought the 14
zone HUB towns to a density floor (vendor + 3 voices + 2 lore); what remains bare is the **28 non-hub
settlements**, which are a single map room + one generator-stamped resident. This campaign gives them
real interiors, one settlement per slice, starting with the most incongruous gap: a zone **capital**.

## Problem
`caeloria_city` is the CAPITAL of Caeloria (the heartland kingdom, the centre of the world on the
map) and yet has no interior at all - a stranger walking the high road reaches the seat of a kingdom
and finds a bare signpost. A capital should be the richest room in its zone, not the emptiest.

## Constraints
- Pure data, no code: a new town is `authored/<town>.yaml` + `quests/<town>.yaml` through the
  existing pipeline (`kernel/world/authored_towns.py`) - no engine, registry, or boundary change.
- In-canon: Caeloria is the heartland of golden plains, gold-crowned towers, the high road, and the
  Order of KNOWING (rule by record, not the sword). Every room, voice, and item serves that identity;
  nothing contradicts `canon.yaml` (Caeloria is CANON_LOCKED).
- Clears the density floor with margin: 5 rooms, 4 cross-referencing voices, a vendor, 2 lore items,
  and a quest of the Knowing shape. Reuses a REAL gatherable (`meadowfoil`, the plains herb) for the
  merchant's buy - a closed loop with the draughts it sells, not a dead flavour entry.
- Every subarea reachable from the hub; the boundary exit `out: <hub>` keeps the per-file exit gate
  happy; the quest walks to its terminal state (proven by a test, not asserted).
- No em/en dashes (fleet rule), interviewer-facing prose.

## Decision
Approved (K4 in the keel batch): author the bare settlements to real interiors, capitals first.
Slice 1 is Caeloria City - a Knowing-order capital whose quiet, bureaucratic conflict (a lost page
of the heartland charter) echoes the world's spine (the written record that holds the realm while the
reaches fray), with the culprit left unproven. The remaining 27 bare settlements follow, one per
slice, on the same pattern; this record covers the campaign and its first town.

## Alternatives considered
- **Deepen the already-authored hub towns further (toward Greenhold's 10-room tier).** Deferred: they
  already clear the density floor; a bare capital with ZERO interior is the larger, more glaring gap.
- **Author a lesser bare town first.** Rejected for slice 1: a capital is the highest-visibility gap
  (the seat of a kingdom) and sets the quality bar for the pattern.
- **Invent a new material for the merchant's buy.** Rejected: reuse a real gatherable (`meadowfoil`)
  so the buy is a live economy loop, not a dead entry (correspondence: no claim without the thing).

## AI contribution
AI-drafted the Caeloria City interior (5 rooms, 4 voices with cross-referencing topic trees, a
vendor, 2 lore items) and its quest (`The Twelfth Page`), in Josh's established Caeloria/Knowing
canon, plus the quest-walk test twin. The world's voice, canon, and acceptance of the prose are
Josh's.

## Human modification (the keel)
Josh gated K4 as a keel decision and approved the batch. He owns the world's voice: the canon the
prose must serve, and the review/acceptance of the writing itself. AI drafts towns to the pattern;
Josh keeps the keel (what the heartland IS) and edits the prose to his ear.

## Tests / evidence
- `tests/test_authored_towns.py`: the town raises and clears the density floor (vendor + 3 voices +
  2 lore); every subarea is reachable from its hub; the world composes it into the real Aethryn map;
  the quest walks to `done` and grants Knowing standing.
- World boots with the capital merged (5 rooms + hub wired + quest registered); journey gate green.
- `ruff` + `mypy` clean; no fancy dashes. CI runs the full matrix before merge.

## What Josh learned
*(For Josh, per doctrine: e.g. edit a voice to his ear, add a fifth room or a second quest of a
different shape, or judge whether the capital reads like the centre of a kingdom.)*

## Final decision
Josh's, at the merge junction and of this record. The prose is his to accept or rewrite; the level-4
ownership claim is his to make on the Career Board.

## Uncertainty / review point
27 bare settlements remain; this is a continuing campaign, one slice at a time, capitals and
high-traffic early-zone towns first. Whether a capital should exceed the floor toward Greenhold's
full 10-room tier (a throne hall, more quests) is a scope dial for Josh.
