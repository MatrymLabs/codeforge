# Aethryn Navigation Migration Plan

## Finding

The authored map is a 14-zone macro graph. Its zone-to-zone links are mostly cardinal, while hubs
use named spokes and child locations use `out`. This is a valid content model for a macro map but a
weak teaching model for a player-facing room graph. Convert the presentation and aliases first; do
not rewrite the map blindly.

## Order

1. Add exit metadata: canonical direction, display label, alias, reciprocal id, one-way/locked/hidden
   state. No behavior change.
2. Migrate Creator's Hall and the first onboarding route. `up`, `out`, and station names remain safe
   aliases where they do not collide.
3. Migrate each major hub and transition route in zone order: Veridia, Duskwood, Caeloria, Eldryn,
   Frostspire, Zhaar, then the remaining eight zones.
4. Add `exits` and compass output to every room payload and update maps/help.
5. Observe alias usage for two releases. Deprecate only with a release note and opt-in warnings.

## Mapping policy

`north — Frostspire Peaks`, `east — Caeloria`, and `out — Veridia` are canonical where the existing
geometry proves those relationships. A named spoke such as `greenhold` becomes `east — Greenhold`
only if the world author supplies a spatial placement; otherwise it remains a named destination
exception and is displayed as `greenhold — Greenhold [named route]`.

Settlement `out` links are not automatically broken reciprocals: the parent hub may keep a named
portal label. The audit must record the semantic pair (`parent -> settlement`, `settlement -> parent`)
and whether `in` is intentionally absent. A missing reciprocal is an error only when the author marks
the pair physically reciprocal.

## Compatibility

Legacy words are aliases under `go` and direct movement only when unique. Exact cardinal commands
win over named matches. A legacy alias never bypasses a lock or owner gate. Help shows `north (n)`
first and `greenhold` as an alias/route label second.

## Rollback

Exit metadata is versioned. Roll back by selecting the prior map version, preserving the new aliases
for one compatibility window. Restore from the seed backup before any persistent migration; runtime
projection changes are restart-reversible.

## Tests

Snapshot every migrated room at narrow and standard widths; validate reciprocal metadata, duplicate
directions, dangling destinations, self-loops, hidden/locked distinctions, command collisions, and
text/GMCP parity. Include a property test that every canonical primary exit in a flagged hub meets
the threshold in `AETHRYN_EXIT_DIRECTION_POLICY.yaml`.

