# Bench Report: WO-XLSX-GO-1

## Result

The new `native/sheets` Go module reads named-sheet cell values using only `archive/zip` and
`encoding/xml`. No dependency was added. It bounds workbook bytes, declared member sizes, total
declared expansion, and actual member reads; hostile input returns named errors and does not panic.

The reader is a third-product shape: a standalone converter component, unlike the engine pour and
the cartridge tool. It is not yet a PROVEN lane record by itself until the Principal Engineer accepts
and merges the product.

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

## Awaiting Principal Engineer

Decision needed on the Go 1.26.5 standard-library vulnerability/toolchain upgrade and acceptance of
the nested-module verification command. No dependency was added and no out-of-scope fix was made.
