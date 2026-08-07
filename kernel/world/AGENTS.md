# World Kernel Rules

- The engine consumes CodeForge seed records. New Aethryn systems must adapt to existing seed
  formats rather than creating a parallel runtime graph.
- Canon comes from `content/seeds/aethryn/canon.yaml`; region topology comes from
  `content/seeds/aethryn/world_graph.yaml`. The map poster is never a topology input.
- Validators must fail with the record id, field or path, violated authority or rule, and a corrective
  action. A boolean without an actionable finding is insufficient.
- Generators are pure or explicitly seeded. Runtime world assembly never calls a model. A package
  rebuild must be reproducible from the packet, source digests, seed, and generator version.
- Every generated record has provenance and remains `GENERATED_LOCAL` unless an explicit human
  authorization is present. Keep manifests and old packages available for restore.
- Preserve state-as-canonical and rendering-as-projection. Validators and compilers must not mutate
  live runtime state.
