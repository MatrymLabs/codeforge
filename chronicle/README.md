# The Chronicle (the ship's memory)

This directory is the Chronicle's retained store: an append-only, content-hashed, hash-chained
`ledger.jsonl` that the ship reads back. Unlike `arc-evidence/` and `security-evidence/` (which
are git-ignored, regenerated evidence), the Chronicle is **git-tracked on purpose**: retained
evidence is the whole point (records + safety), and each record is reproducible from the commit
it cites.

- **Written by** `parts/chronicle.py` (`append()`), only through its validating gate.
- **Read by** the `chronicle` verb (read-only view, incl. `chronicle trend <name>`,
  `chronicle provenance <node>`, and `chronicle incidents`) and, from slice 1b, ARC's `evidence`
  dimension.
- **Kinds:** `evidence` (a retained, cited gate verdict; slice 1), `metric` (a `{name, value}`
  trend point; slice 2, e.g. `make trend` records `engine_tick.median_us`), `edge` (a
  `{from, relation, to}` PROV-O provenance link; slice 3, e.g. `make arc-verdicts` records that
  the evidence `wasGeneratedBy` the gate run and the release `wasInformedBy` the evidence), and
  `incident` (a FRACAS `{what, severity, corrective_action, status}` record; slice 4 - a blocked
  release opens one automatically). Later slices add `ai-eval`.
- **Integrity:** every record carries a `content_hash` over its fields plus the prior record's
  hash. Any edit to a past record breaks the chain and fails loud on read (`ChronicleError`); a
  dishonest memory is worse than an error.

See `docs/reports/2026-07-13-chronicle-design.md` for the design and `parts/chronicle.py` for the
CARD. The `ledger.jsonl` appears here once a gate files its first record (e.g. `make arc-verdicts`).
