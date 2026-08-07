# Aethryn Engineering Rules

These rules apply to Aethryn work in this repository.

- Authority order is `content/seeds/aethryn/canon.yaml`, the Aethryn Lore Bible, `world_graph.yaml`,
  `generation_contract.yaml`, the approved master design, current structured seed data, authored
  local content, then non-conflicting legacy material.
- Never rename Aethryn or any of its fourteen regions, change threat bands, relocate a Seven Crown,
  make the Divine Strike accidental, make Netharion natural-born, answer unresolved global questions
  as fact, or present superseded metaphysics as current canon.
- `world_graph.yaml` owns playable region topology. Map artwork gives orientation only. Decorative
  routes and shared seas do not create room exits unless a separate approved route is authored.
- Every generated record needs a stable id, canon status, source design ids, seed, generator name and
  version, provenance, and a content digest where the record is published.
- Generation is offline and deterministic. Runtime startup and package materialization must never
  call a model. Same inputs, seed, and generator version must produce the same output digest.
- Generated material stays `GENERATED_LOCAL` until a human explicitly authorizes another status.
  Unknown and unresolved material must remain explicit, disputed, or rumor-only.
- Validate before publication. Publish from a staging package with a manifest and digest, keep the
  previous package restorable, and never overwrite a package without a recorded rollback path.
- Run focused tests while working, then the applicable full suite and repository gates. Report red or
  skipped checks honestly. New commands require an engine or compiler reachability test.
