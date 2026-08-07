# Aethryn Seed Rules

- `canon.yaml` is the locked identity source. `world_graph.yaml` is the canonical topology source.
  Do not derive playable exits from the map poster or decorative map routes.
- Preserve Aethryn, all fourteen region names, threat bands, Seven Crown placements, the intentional
  Divine Strike, Netharion as the first artificial god, and the open questions.
- Use `CANON_LOCKED`, `CANON_WORKING`, `AUTHORED_LOCAL`, `GENERATED_LOCAL`, and `RUMOR` honestly.
  Never promote generated content silently.
- New packets and seed records need stable ids and provenance. Generated content must carry its
  packet id, source design ids, seed, generator name, version, and digest in the package manifest.
- YAML is authored data, not a license to invent global lore. Use `unknown`,
  `intentionally_unresolved`, `authoring_required`, `rumor_only`, or `not_yet_modeled` where evidence
  is incomplete.
- Validate every batch and packet before materialization. Preserve a previous package so publication
  can be rolled back. Runtime must not depend on a model call.
