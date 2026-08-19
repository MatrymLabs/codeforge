# Bench Report: WO-XLSX-GO-1

## Result

The new `native/sheets` Go module reads named-sheet cell values using only `archive/zip` and
`encoding/xml`. No dependency was added. It bounds workbook bytes, declared member sizes, total
declared expansion, and actual member reads; hostile input returns named errors and does not panic.

The reader is a third-product shape: a standalone converter component, unlike the engine pour and
the cartridge tool. It is not yet a PROVEN lane record by itself until the Principal Engineer accepts
and merges the product.

## Amendment 2: XML recursion reachability

Yes: a deeply nested XML bomb inside a `.xlsx` reaches `GO-2026-6088` in this reader. The workbook
bytes are untrusted at `ReadSheet`; `reader.go` constructs four `xml.Decoder` instances over
workbook, relationships, shared-strings, and worksheet bytes. Cell parsing also calls
`Decoder.DecodeElement`. Go 1.26.5 has no sufficient recursion-depth guard for this path, so a
deeply nested XML member can exhaust the stack before the reader returns a named error. This fixture
was missing from the original hostile-input suite and is a blocking security finding, not a reason
to add a dependency. The advisory is fixed in Go 1.26.6; the verification environment used Go
1.26.5 (`go.mod` currently declares Go 1.25 and does not itself upgrade the toolchain).

## Generality proof from Intake Form v1 and Blueprint v1

Fields that broke or were missing for this product:

- `accepts_untrusted_input` says hostile fixtures are required, but it does not say the required
  safety policy: bounded archive/member reads, declared-size checks, named error classes, and no
  panics. Those had to be specified by the product.
- Neither schema has an input format/structure field for ZIP/XML workbooks, a named-sheet selector,
  or cell-value semantics (inline strings, shared strings, numbers, booleans, and unsupported
  formula/style behavior).
- Neither schema captures the standalone-binary requirement or the “no runtime install” product
  property that caused this order to use Go.
- `expected_output` is broad enough to say “cells/table,” but it does not define deterministic table
  rendering or the source-integrity hash contract used by the proof.
- The Blueprint's `modules_consumed` is measured after implementation and has no place to record
  the standard-library-only archive/XML boundary or the explicit dependency prohibition.

Fields the form had but this product did not use as operational controls:

- `persists_state` was false, so there are no persist/restart/survive stages.
- `must_run_detached` was false; the reader is a library and the proof is a local staged process.
- `input_provenance_constraints` was not enforced by the reader API; the proof synthesized its own
  workbook, so provenance remained a fixture discipline rather than a parser decision.
- `target_user` did not change the reader surface; the named-sheet API and deterministic text table
  were dictated by the requested converter behavior.

The form's `languages` field did prove useful: Go was a required lane, and the Blueprint's
`language_lanes` record expressed Go as the product lane rather than a Python fallback. That is a
Go-shaped fact the two Python-derived drafts could not supply.

## Failure before repair

- The exact root command `go test ./native/sheets/...` failed because this repository uses nested Go
  modules and has no root `go.mod`/`go.work`: `directory prefix native\\sheets does not contain main
  module or its selected dependencies`.
- The module-local test then exposed `archive.Reader undefined` in the initial reader implementation.
  That compile defect was repaired before the green module run.
- First `make lint-go` found 13 lint issues in the new files; all were repaired. The rerun reports
  `native/sheets` -> `0 issues`.

## Proof runs

- `go test ./...` from `native/sheets` -> PASS.
- `go vet ./...` from `native/sheets` -> PASS.
- `make lint-go` -> PASS for `native/edge`, `native/sheets`, and `native/spine`.
- `govulncheck ./...` -> one toolchain finding, `GO-2026-6088` in `encoding/xml@go1.26.5`, fixed in
  Go 1.26.6. This is standard library/toolchain state, not a dependency to add; it is reported for
  a Principal Engineer decision.
- The broad `make check` ran and reached the Python suite but failed one pre-existing parity test:
  `tests/test_env_parity.py::test_the_real_repo_has_no_unmarked_shebang_scripts`, reporting
  `scripts/cast_selfproof.py`. It is outside this order's allowlist and was green on the reviewed
  self-proof target branch; it was not changed here.

## Pattern screen and Part signals

- **lane echo:** untrusted-input boundaries, bounded reads, deterministic output, and integrity
  evidence echo existing parser/proof practice in the persistence/commands/events/integration lane.
- **catalogue match:** no XLSX, ZIP/XML, or bounded-archive Part matched in Certified Tier or the
  Working Shelf; both tiers were searched.
- **recurrence:** hostile-input refusal and staged sabotage recur; the Go implementation is a
  cross-language fitting candidate, not a certified Part.
- **reimplemented:** none observed.
- **generalizable:** a stdlib-only bounded ZIP/XML reader with named refusal errors.
- **friction:** the nested Go module boundary makes the requested root `go test ./native/sheets/...`
  command invalid without a repository-level workspace file; adding one was outside scope.

## Narrowed Python-native inventory

The amended six-file break test is clean. Remaining tracked occurrences outside that allowlist are
listed here as findings only and were not edited:

```text
Workshop/FLEET_OVERVIEW_FOR_REVIEW.md:20
Workshop/rd/01-claims/master-corpus-2026-08-01.md:36
Workshop/rd/02-experiments/bench-parts-forging/EXP-14-smell-engine/hardware-card.md:23
Workshop/rd/02-experiments/bench-parts-forging/EXP-14-smell-engine/smell_engine.py:10
Workshop/rd/04-verdicts/TECHNOLOGY_WATCHLIST.yaml:92
codeforge/Makefile:586
codeforge/README.md:12
codeforge/adapters/web/index.html:36
codeforge/catalog/parts.yaml:1739, 1757, 1775, 1793, 1811, 1829, 1847, 1865, 1883
codeforge/docs/architecture_c4.md:20
codeforge/docs/frameless_python.md:11, 19
codeforge/docs/project_management.md:14
codeforge/docs/technology_intake.md:4
codeforge/intake_ledger.toml:1
codeforge/kernel/intake.py:1, 3
codeforge/kernel/shelf/smell_engine.py:10
codeforge/registry/designations/modules.json:5048
```

The two pre-existing untracked self-proof trees also contain occurrences; they remain outside this
order and are not edited.

## Awaiting Principal Engineer

Decision needed on the Go 1.26.5 standard-library vulnerability/toolchain upgrade and acceptance of
the nested-module verification command. No dependency was added and no out-of-scope fix was made.
