# ADR-0008: Subnet designations (retire the Borg/Unimatrix designation format)

Date: 2026-07-15 · Status: accepted (approved by Josh) · Supersedes the format in
[CLASSIFICATION_SYSTEM.md](../classification/CLASSIFICATION_SYSTEM.md).

## Context

The Classification Registry filed every object with a "Borg"/Unimatrix designation:
`TYPE-UM##-S##-N###-SEQ-REV` (e.g. `MOD-UM04-S01-N001-044-R0`). Two problems surfaced:

1. **It read as the wrong scheme.** The Hardware Store catalog had already moved to a
   subnetting address (`domain.ordinal`, e.g. `12.002`) under the V3 redesign
   ([catalog_v3_redesign.md](../hardware_store/catalog_v3_redesign.md)). The registry still
   spoke Borg. The ship should label code with **one** principle.
2. **A real mis-filing.** `telnet_codec` (a reusable Hardware Store part) was filed as a game
   module in `UM04` (Game systems) instead of `UM05` (Hardware Store), where its siblings
   (`circuit_breaker`, `token_bucket`, `stream_framer`) live.

Evidence that shaped the design (from a full blast-radius audit):
- All 188 filed rows use `S01/N001/R0` uniformly, so sector/node/revision carry no information.
- The engine (`parts/registry.py`) re-derives structural fields from the designation string in
  `__post_init__`, so the string is the only load-bearing part of a row.
- The catalog's `domain.ordinal` is an **alphabetical, non-stable display aid**; the registry's
  sequence is a **stable minted integer**. Identity is the frozen `label`, never the address.
- The two taxonomies are **orthogonal**: registry domains classify *where a thing lives in the
  ship/world* (Workshop, City, Game, Hardware Store, ...); catalog domains classify *what
  engineering problem a reusable part solves* (Validation, Parsing, Resilience, ...).

## Decision

Adopt the V3 **four-layer identity model** across the registry, additively and losslessly:

- **Identity** (permanent, frozen): the `label` (room key, module name, verb). Unchanged. The
  stable key that every cross-reference resolves to.
- **Address / designation** (new format): `TYPE-DD.NNN` where `DD` is a 2-digit domain code and
  `NNN` is the stable ordinal preserved from the old sequence. Example: `MOD-04.009`,
  `RM-03.001`, and `MOD-05.NNN` for the corrected `telnet_codec`.
- **Legacy alias**: each row keeps its old Borg designation in `aliases`, so
  `registry show MOD-UM04-S01-N001-009-R0` still resolves. Nothing that referenced a Borg id
  breaks.
- **Metadata**: `tags`, `depends_on`, `related` (labels, not ids) unchanged.

Registry domains keep their ten world meanings, renumbered `UM01..UM10 -> 01..10`. Registry
domains (world) and catalog domains (engineering) are both `domain.ordinal` subnet addresses,
disambiguated by TYPE prefix (`MOD-05.x` world-domain 05 = Hardware Store; `PRT`/catalog
`12.002` engineering-domain 12 = Parsing). Sector/node/revision are dropped from the address
(they were always defaults); the model extends to `DD.SS.NNN` later if a domain grows subsystems,
without renumbering (the ordinal is the filing aid, the label is identity).

## Consequences

- The migration touches: the engine regex/domains/mint/`__post_init__`/display; the 188 rows
  (rewrite `designation`, add Borg alias, correct `telnet_codec` 04->05, remap 5 Borg cross-refs);
  the schema; `forge.py`'s 28 command ids; the format-pinning tests; and the classification docs.
- A gate keeps it honest: every module stays filed, every designation matches the new format, and
  the shipped registry validates clean (`test_registry`), so no loose leaf can regrow.
- Rollback is a branch revert; identity (labels) never moved, so no save/seed/data migration.
