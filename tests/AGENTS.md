# Aethryn Test Rules

- Test canon restrictions, open-question leakage, hierarchy, topology, reciprocal exits, settlement
  dependencies, economy, ecology, dungeon grammar, packet validation, determinism, provenance,
  materialization, rollback, CLI output, and Veridia persistence.
- Use temporary directories and injected paths for package tests. Tests never write the shipped seed
  or live database.
- Hostile cases are required: mixed case, symbols, near-miss ids, dangling exits, unauthorized
  status promotion, missing provenance, conflicting sources, and changed generation versions.
- Assert actionable validation text, not only an error count. A successful test must prove the system
  reaches the intended engine or compiler path.
- Runtime tests must not call a model or network. Same packet plus seed plus version must have the
  same digest, and a prior materialized package must be restorable.
