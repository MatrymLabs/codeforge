# The Chronicle (the ship's memory)

This directory is the Chronicle's retained store: an append-only, content-hashed, hash-chained
`ledger.jsonl` that the ship reads back. Unlike `arc-evidence/` and `security-evidence/` (which
are git-ignored, regenerated evidence), the Chronicle is **git-tracked on purpose**: retained
evidence is the whole point (records + safety), and each record is reproducible from the commit
it cites.

- **Written by** `parts/chronicle.py` (`append()`), only through its validating gate.
- **Read by** the `chronicle` verb (read-only view) and, from slice 1b, ARC's `evidence` dimension.
- **Kinds (slice 1):** `evidence` (a retained, cited gate verdict). Later slices add `metric`,
  `incident`, `ai-eval`, and `edge` (provenance).
- **Integrity:** every record carries a `content_hash` over its fields plus the prior record's
  hash. Any edit to a past record breaks the chain and fails loud on read (`ChronicleError`); a
  dishonest memory is worse than an error.

See `docs/reports/2026-07-13-chronicle-design.md` for the design and `parts/chronicle.py` for the
CARD. The `ledger.jsonl` appears here once a gate files its first record (e.g. `make arc-verdicts`).
