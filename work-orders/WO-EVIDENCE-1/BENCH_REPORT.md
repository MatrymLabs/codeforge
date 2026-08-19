packet_id: WO-EVIDENCE-1
pr_url: none opened by Codex
status: COMPLETE

## Result

Added a validated `EvidenceManifest` object, four-valued `Result` enum, exception record,
JSON writer, artifact SHA-256 helper, construction validation, tests, and the registry designation.
No gate, Makefile, or CI wiring was added.

## Required fields and invariants

The manifest carries blueprint id/version, work order id, proof run id, tool/version, commit SHA,
exact command, exit code, result, artifact SHA-256, producing bench, verifying bench, and exception
owner/reason/expiration. `PASS` with a nonzero exit code is refused, so a tool crash cannot become
PASS. The only accepted results are PASS, FAIL, UNMEASURABLE, and NOT_APPLICABLE.

## Break/refusal evidence

The focused tests cover both required refusal twins. Direct construction output:

    missing verifying_bench EvidenceManifestError verifying_bench is required
    exception missing expiration EvidenceManifestError exception expiration is required

The tool-crash twin also refuses `exit_code=1, result=PASS` with `PASS result requires exit_code 0`.

## Commands run

- `.venv\\Scripts\\python.exe -m pytest tests/test_evidence_manifest.py -q`
  - exit 0; `9 passed in 0.29s` (after the final serializer/type fixes)
- `make lint-python`
  - exit 0; ruff format and ruff check clean.
- `make typecheck-python`
  - exit 0; mypy reports no issues in 405 source files.
- `make check`
  - exit 0; `5427 passed, 57 skipped, 1 xfailed`, 93.38% coverage, including registry
    completeness and Bandit.

## Store search

Searched both required tiers before writing:

- Certified Tier `hardware-store/catalog/`: found `source-monitor` PRT-0003. Its injected
  fetch seam and failure-as-value discipline were reviewed and borrowed conceptually; it does not
  model evidence manifests and was not copied or consumed as an implementation.
- Working Shelf `codeforge/catalog/parts.yaml`: no applicable evidence-manifest Part found.

Result: one adjacent certified pattern, no directly applicable Part.

## Files touched

- `kernel/evidence_manifest.py`
- `tests/test_evidence_manifest.py`
- `registry/designations/modules.json`
- `work-orders/WO-EVIDENCE-1/BENCH_REPORT.md`

## Extraction signals

reimplemented: no directly applicable Part existed; the writer is a small standalone schema Part.

recurrence: explicit validation at construction and failure-as-value verdict handling recur from
the source-monitor discipline, but this is a new evidence-domain occurrence.

generalizable: the four-valued enum, nonzero-exit PASS refusal, and required verifying bench are
usable by future evidence producers without wiring this Part into a gate.

friction: none; source-monitor's injected seam was clear and no implementation dependency was
needed.

pattern_shapes: immutable validated value object, explicit enum, normalized exception records,
deterministic JSON writer, and SHA-256 helper.

## Pattern screen

lane_echo: none observed in Codex's persistence, commands, events, transactions, world-graph, or
integration lane.

catalogue_match: source-monitor PRT-0003 is adjacent only; no catalogue Part models this schema.

recurrence_check: failure-as-value and injected seams are recorded as adjacent patterns, not
claimed as a direct reuse.

verdict_note: source-monitor was consumed conceptually for failure discipline; no code was copied,
and the manifest remains un-wired as required.
