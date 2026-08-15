# WO-2D-1 seam surface scout

Date: 2026-08-14
Repository: codeforge
Order: WO-2D-1

## Method

The dispatch blast-radius command was run against the current `origin/main` checkout:

```text
$ grep -rn 'session\.location' --include=*.py kernel/ adapters/ forge.py | grep -v build/ | wc -l
123
$ grep -rl 'session\.location' --include=*.py kernel/ adapters/ forge.py | grep -v build/ | wc -l
27
```

The classification rule is the order's rule: a write to `session.location` is an assignment; a
room-scoped lookup, broadcast, roster, or renderer input is a room-label consumer; a direct
comparison, persistence or serialization use, or string-derived use is a genuine position query.
Local room snapshots used only to detect a room change remain room-label consumers unless they
cross the position boundary.

## Counts

| classification | count |
| --- | ---: |
| room-label consumer | 94 |
| assignment | 8 |
| genuine position query | 21 |
| total | 123 |

Assignment sites:

```text
kernel/world/ranks.py:45
kernel/world/combat.py:274
kernel/world/characters.py:284
kernel/world/travel.py:86
kernel/domains/game_session.py:104
forge.py:2279
forge.py:2300
forge.py:2683
```

## Genuine position sites

Each site below treats the room label as more than a room-scoped key.

```text
kernel/world/events.py:101
  Compares the session location with a room while filtering event recipients.

kernel/world/creator_workshop.py:226
  Compares the location with the Planning Table literal for a permission boundary.
kernel/world/creator_workshop.py:277
  Compares the location with the Statistics Wall literal for a permission boundary.
kernel/world/creator_workshop.py:340
  Compares the location with a requested room in the owner-at-station predicate.
kernel/world/creator_workshop.py:345
  Tests location membership in the Workshop room set for a permission boundary.
kernel/world/creator_workshop.py:457
  Compares the location with the Publishing Portal literal before publishing.
kernel/world/creator_workshop.py:471
  Compares the location with the Publishing Portal literal before rollback.

kernel/world/party.py:72
  Compares a session location with a room while determining party presence.

kernel/world/abilities.py:166
  Compares another actor's location with the session location while selecting allies.
kernel/world/abilities.py:305
  Compares another actor's location with the session location while selecting targets.

kernel/world/travel.py:135
  Compares the requested route destination with the current location.
kernel/world/travel.py:137
  Passes the current location as the start node to the navigation path query.

kernel/gmcp.py:197
  Serializes the location as the protocol's `num` field for an unknown room.
kernel/gmcp.py:199
  Serializes the location as the protocol's `num` field for a known room.

kernel/world/characters.py:219
  Persists the location in CharacterRecord and therefore the durable character store.

kernel/domains/game_session.py:115
  Stores the location in a restart-parity backup snapshot.

adapters/gateway.py:770
  Stores the location as the cross-process room-change baseline.
adapters/gateway.py:804
  Compares the current location with that cross-process baseline.

forge.py:2276
  Compares the resolved destination with the current location to detect movement.
forge.py:2352
  Interpolates the location into the `room:` item-resolution scope string.
forge.py:2779
  Compares a routed signal's room with the current location.
```

## Verdict for WO-2D-2

**Large.** The majority of the surface is safely room-label keyed, but 21 sites cross the seam.
The riskiest site is `kernel/world/characters.py:219`: location is persisted as durable character
state and is restored at `kernel/world/characters.py:284`. The next risk cluster is the six
workshop permission checks in `kernel/world/creator_workshop.py`, where a mistaken derivation could
change authorization rather than only presentation.

The 94 room-label consumers are the favorable news: they can continue to receive a derived
`room_of(position)` value. The 8 assignments are the engine placement seam. The 21 genuine sites
need explicit decisions in 2D-2; no source change is made by this scout.

## Store search

Certified Tier, searched first: `../hardware-store/catalog/`. No reference-classifier or call-site
survey Part found. Working Shelf, searched second: `catalog/parts.yaml`. No field-usage classifier
found. Both searches were empty for this capability; no Part was consumed.

## Proof and scope

```text
Source files modified: 0
Report files created: 1
References classified: 123 across 27 files
```

The required repository gate remains the order's verification command:

```text
cd codeforge && make proto && make check && test -f reports/2026-08-14-seam-surface-scout.md
```

No source file, test file, or configuration file was modified.

## Blueprint migration review

The effective allowlist for WO-2D-1 is this report file only. The prose sweep found no retired-term
prose in the allowlist, so no prose migration was required.

Identifier punch list: empty. The allowlisted report contains no `seed_root`, `seed_path`,
`load_seed`, retired class name, seed schema key, public API, wire field, or CLI flag. No Class 2
identifier was renamed.

Contract flags: none in the allowlist. Source identifiers and contracts remain untouched because
WO-2D-1 does not authorize their files.
