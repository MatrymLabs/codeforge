# WO-XML-DEPTH-1 Bench Report

packet_id: WO-XML-DEPTH-1
repository: codeforge
branch: codex/verify-wo-rev-1043
status: READY_FOR_REVIEW
verdict: READY_FOR_REVIEW

## Changed

Added one bounded XML token source in `native/sheets/reader.go`. All workbook, relationship,
shared-string, worksheet, cell, and element-text scanners use it. Start tokens increment depth;
an element beyond 10,000 levels returns an error wrapping `ErrInvalidXML`.

Added assertion-locked fixtures for worksheet skeleton, workbook.xml, and sharedStrings.xml,
plus the existing deep-cell fixture and ordinary-cell calibration.

## Failure before repair

The new tests were run before the decoder routing change:

```text
--- FAIL: TestHostileXLSXInputsRejectDeepNestingOnEveryMember
    worksheet_skeleton: error = <nil>, want ErrInvalidXML
    workbook: error = <nil>, want ErrInvalidXML
    shared_strings: error = <nil>, want ErrInvalidXML
FAIL
```

## Proof runs

```text
cd native/sheets && GOFLAGS=-buildvcs=false go test ./... -count=1
ok   codeforge/sheets
?    codeforge/sheets/proof [no test files]

make proto
regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go

GOFLAGS=-buildvcs=false make check
5432 passed, 57 skipped, 1 xfailed
Required test coverage of 85% reached. Total coverage: 93.37%
```

The full gate exited 0. The native package proof and the full gate were run in this session.

## Hardware Store search

Certified Tier: no exact bounded-XML or workbook hostile-input Part matched.
Working Shelf: no exact XML-depth Part matched; adjacent parser and hostile-input patterns were
reviewed and not consumed.

## Pattern screen

lane_echo: persistence, commands, events, transactions, world graph, and integration were
screened; this change is isolated to workbook parsing and hostile-input refusal.

catalogue_match: no exact Certified Tier or Working Shelf Part matched the single bounded token
source design.

recurrence_check: hostile-input refusal and parser resource boundaries recur; this change closes
the previously unbounded workbook-member paths without changing size caps or public APIs.

verdict_note: READY_FOR_REVIEW. All four XML scanner paths now share one depth boundary, and the
three new member-level fixtures plus the existing cell fixture pass.

## Reusable Part signals

reimplemented: none observed; no existing Part covered bounded XML token scanning.

recurrence: hostile-input fixtures and parser resource limits recur across workbook readers.

generalizable: put resource accounting at the shared token boundary, then test every caller path
and retain an errors.Is contract.

friction: Windows required the direct approved patch utility when the sandbox helper was
unavailable; full multi-language verification completed successfully.

## Boundary

Only `native/sheets/reader.go`, `native/sheets/reader_test.go`, and this report were touched.
No merge or public API change was made.
