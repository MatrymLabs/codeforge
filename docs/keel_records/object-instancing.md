# Keel Record: Object instancing (prototype + clone), slice 1

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction design decision (a change to the central item model) and its first build slice.
Per the doctrine, AI proposes and Josh approves; **AI does not assign ownership**. The level-4
ownership claim and the "what I learned" reflection below are left for Josh to complete when he can
defend the design to an interviewer.*

- **Build:** the prototype/instance foundation for items - a `prototype` field, a `clone(prototype,
  location)` spawn primitive, and prototype-aware matching for door keys and quest pickups
  (`parts/items.py`, `parts/seed.py` Item, `parts/doors.py`, `parts/generate.py`, `forge.py`).
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Give CodeForge object instancing: a seed label is a PROTOTYPE (a template), and runtime items are
INSTANCES cloned from it. This is the keystone the legacy-MUD archaeology kept hitting - area
repopulation, loot drops, and mob/item spawns all need "mint a fresh copy of this thing," which a
singleton, label-keyed item model cannot express. This slice builds only the foundation and the
spawn primitive; repop/loot/spawn-policy build on it later.

## Problem
`items.ITEMS` is `dict[label, Item]` with exactly one item per seed label; the label IS the identity.
There is no way to have two of a thing, so a reset that restocks an item would duplicate a quest item
or pull it from a player's pack, and loot cannot drop a copy. Naively fixing this invites a big-bang
re-key of every item to instance ids (with snapshot migration and every label-equality site touched
at once). The problem was to introduce instances additively, without disturbing a single existing
world.

## Constraints
- **Smallest useful slice:** a `prototype` field + `clone()` + two prototype-aware equality checks.
  No gameplay feature yet; repop/loot are later slices.
- **Zero behavior change:** a seed-placed item is its own prototype (`prototype == label`), so it
  stays keyed by its label and every existing lookup, render, and save is byte-identical. Existing
  worlds and the whole suite pass unchanged.
- **Contained blast radius:** only two places compared an item by its seed label - a door's key
  (`_key_fits`) and a quest's `on_take`. Both now compare `prototype_of(iid)`, which returns the
  label for a seed item, so the singleton case is unchanged and a clone counts as the real thing.
- **Architecture laws honored:** clone mutates canonical state through validated logic; it fails
  loud (`ItemError`) on an unknown prototype rather than spawning a ghost. Prototypes are captured
  pristine at load so clone works even after every instance has left play.
- **Persistence deferred, honestly:** `save.py` snapshots `{iid: location}`; seed items persist as
  today. Instance persistence (rebuilding cloned instances on restore) is **slice 2** - no shipped
  seed creates clones yet, so save is unaffected now, and this is recorded as a known gap, not hidden.
- **Critical-junction rule:** changing the central item model stops for a keel decision before code.

## Decision
Approved by Josh (Fork A, foundation-only) after a design proposal weighing **A. additive
prototype+clone** vs **B. full re-key to instance ids**. Chose A: additive, reversible, zero
behavior change, with instance persistence as a follow-up slice.

## Alternatives
- **B. Full re-key now:** cleaner long-term identity, but a one-shot migration of every item to
  instance ids, snapshot migration, and every existing test/world reconciled at once. Rejected as
  too big a first step for a core-model change; A reaches the same model incrementally.
- **A prototype registry independent of instances** (chosen for robustness): `PROTOTYPES` holds the
  seed templates, so clone does not depend on a live instance still existing.

## AI contribution
Mapped the blast radius (7 modules touch `ITEMS`; only 2 label-equality sites), proposed A vs B,
implemented the foundation and tests.

## Human modification
*(pending Josh)*

## Tests / evidence
`tests/test_items.py` (clone mints a distinct instance, copies the template, sets the prototype,
tags the location; cloning twice yields two; unknown prototype fails loud; `prototype_of` fallback),
`tests/test_doors.py::test_a_cloned_key_opens_the_door_by_prototype` (a cloned key opens a door by
prototype), plus the unchanged door/quest/generate/seed suites pinning no regression. `make check`
green.

## What Josh learned
*(pending Josh)*

## Final decision / uncertainty / review point
Foundation merged behind `make check`; **stop for review before slice 2** (instance persistence)
and before the first gameplay consumer (loot/repop). Open question for slice 2: how cloned instances
serialize and restore (extend the world snapshot to record prototype + fields), and whether repop
should cap instances per prototype (a Diku "max exists" rule) to bound spawn growth.
