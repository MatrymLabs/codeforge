# WO-REV-1043 Bench Report

packet_id: WO-REV-1043
repository: codeforge
review_branch: codex/verify-wo-rev-1043
review_commit: d963b936
verdict: MERGE

## Review result

I reviewed `origin/integrate/batch-rescue-main-20260818`, the branch containing Claude Code's
eight-conflict resolution. No source changes were made by this review. The merged branch is
current with `origin/main`, its source diff against `origin/main` is empty, and the resolution
survives the required behavioral proofs.

## Four questions

### 1. Branch-side work

No named repair was lost. Proofs run on the merged branch:

- CX-SPINE-1: `make proto` exited 0 and `GOFLAGS=-buildvcs=false make lint-go` reported `native/edge 0 issues` and `native/spine 0 issues`.
- CX-LEAK-1/2/3, CX-DEPS-1, CX-ORDER-1, and CX-FIX5-2: the targeted proof over `test_socket_bus.py`, `test_analytics.py`, `test_edge.py`, `test_loadtest.py`, `test_dependencies.py`, `test_campaign.py`, and `test_schema_guard.py` returned `70 passed, 4 skipped`.
- CX-DEPS-1: `uv lock --check` exited 0.
- CX-NOQA-1: `ruff check .` inside `make check` reported `All checks passed!`.
- CX-RAND-1: the merged `make test` target ran its non-property/non-fuzz suite and returned `5375 passed, 55 skipped, 1 xfailed`; the target remains the intended serial randomized-order surface.
- CX-JUSTIFY-2: the dependency tests were included in the targeted proof and passed.

The full required instrument then returned `5415 passed, 55 skipped, 1 xfailed`, with 93.39%
coverage. Claude's prior `5414 passed, 56 skipped, 1 xfailed, 20 subtests` differs by one pass and
one skip. This verification ran `make proto` first, as the bench requires; the one main commit
added after Claude's measurement changed only Makefile and CI routing, not tests. The difference
is therefore recorded as a measurement finding attributable to generated-code state, not as a
merge defect.

### 2. Go module language floor

The downgrade from `go 1.26.5` to `go 1.25` is correct. `go version` reported `go1.26.5`, both
native modules passed `go test ./...`, and `make lint-go` passed both modules. The module directive
is the minimum language version accepted by tools; the CI toolchain remains 1.26.5. Keeping the
floor at 1.26.5 makes the Go 1.25-built linter reject the module before analysis, which is the
failure the resolution addresses. No capability required by either module was lost.

### 3. Duplicate PY resolver

The resolver is a no-op after duplicate removal, and it still selects the Windows venv:

```text
Makefile:47:PY ?= $(shell test -x .venv/Scripts/python.exe && echo .venv/Scripts/python.exe ...)
.venv/Scripts/python.exe scripts/calibrate_gates.py --only mypy-strict-type-error
```

`git grep` found exactly one `PY ?=` definition. The dry-run proves the resolved executable is
`.venv/Scripts/python.exe`.

### 4. Other merge-kept duplicates

I searched the merge result and the conflict-resolution diff for repeated resolver, gate, engine
annotation, and hygiene-test blocks. Exact definitions occur once: `PY ?=`, `calibrate:`,
`currency:`, `right: Engine`, and `test_every_path_the_security_scan_names_still_exists`.
No second merge-kept duplicate was found. `git diff --check` is clean.

## Proof runs

```text
make proto
regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go

GOFLAGS=-buildvcs=false make lint-go
lint-go: native/edge
0 issues.
lint-go: native/spine
0 issues.

targeted repair tests
70 passed, 4 skipped in 4.84s

make test
5375 passed, 55 skipped, 1 xfailed in 28.09s

make check
ruff: All checks passed!
Contracts: 4 kept, 0 broken.
mypy: Success: no issues found in 404 source files
coverage: 93.39%
5415 passed, 55 skipped, 1 xfailed in 40.23s
```

The full `make check` also passed Rust, Go, Terraform, C, import, native typecheck, Bandit, and
secret-scan lanes. `GOFLAGS=-buildvcs=false` was set for the complete run.

## Pattern screen

lane_echo: persistence, commands, events, transactions, world graph, and integration were
screened through resource teardown, dependency locking, Go module checks, Make orchestration, and
the complete multi-language gate.

catalogue_match: no exact Certified Tier or Working Shelf Part matched merge-conflict review,
duplicate-resolution detection, or cross-language gate verification.

recurrence_check: the repeated class is an instrument measurement boundary: generated artifacts
and toolchain state changed one pass from the earlier report. No second merge-kept duplicate was
found.

verdict_note: MERGE. The resolution preserves the named repairs, the Go floor is justified by the
tooling constraint, the Python resolver remains functional, and the complete gate is green. The
one-count test discrepancy is explained and recorded, not hidden.

## Reusable Part signals

reimplemented: none observed; this was an independent merge review with no source implementation.

recurrence: merge reviews repeatedly need explicit branch ancestry, toolchain state, generated
artifact state, and exact duplicate searches rather than diff inspection alone.

generalizable: verify conflict resolutions by rerunning each repair's own proof, then run the whole
instrument with the same generated-artifact preconditions used by the repository.

friction: Windows PowerShell output is verbose and the full parallel suite count changes when
ignored generated protobuf artifacts are present; the required `make proto` precondition made that
state explicit.

## Boundary

`git diff --stat origin/main...HEAD -- . ':!work-orders'` was empty. Only this Bench Report is
authored for the order. No merge was performed.

IN PLAIN TERMS
- I independently stress-tested the combined branch and reran its important repairs plus the whole build gate.
- That matters because the branch was assembled by resolving conflicts, and a clean-looking merge can silently drop working fixes.
- The useful concept here is verification against behavior: tests and gates answer whether the merged machine still works, not whether the conflict markers merely disappeared.

## FOLLOW-UP 2026-08-19: XML-BOMB FIXTURE AND CURRENT-MAIN RECHECK

status: READY_FOR_REVIEW
merge_commit: b14fb952
branch_state: `origin/main` is an ancestor of this branch; the branch carries the reconciled review history.

### Changed

- Merged `origin/main` with `git merge origin/main`; Git reported an automatic merge with no
  conflicts. This brought in Go 1.26.6 and the self-proof/env-parity fixes.
- Added an explicit XML nesting limit to the native XLSX reader. Cell values are now token-scanned
  instead of delegated to `DecodeElement` so deeply nested unknown elements cannot pass silently.
- Added `TestHostileXLSXInputsRejectDeeplyNestedXML`, a 10,001-level nested workbook cell fixture.

### Failure before repair

`go test ./... -run 'TestHostileXLSXInputs' -count=1` failed first with:

```text
--- FAIL: TestHostileXLSXInputsRejectDeeplyNestedXML
    reader_test.go:111: error = <nil>, want ErrInvalidXML
FAIL
```

### Proof runs

- `go test ./... -run 'TestHostileXLSXInputs' -count=1` -> PASS.
- `go test ./... -count=1` from `native/sheets` -> `ok codeforge/sheets`; proof package has no tests.
- `make proto` -> regenerated protobuf bindings successfully.
- `GOFLAGS=-buildvcs=false make check` -> exit 0; `5434 passed, 55 skipped, 1 xfailed`; coverage
  `93.37%`.

The full-gate count differs from the scratch measurement (`5431 passed, 58 skipped, 1 xfailed`,
`93.36%`). This is the required measurement finding; the optional local tool surface and worker
environment explain the small delta, but the difference is recorded rather than normalized away.

### Hardware Store search

Certified Tier (`hardware-store/catalog/`): no exact XML/XLSX hostile-input or nesting-limit Part.
Working Shelf (`codeforge/catalog/parts.yaml`): no exact XML/XLSX hostile-input or nesting-limit
Part. Adjacent hostile-input and parser/resource-limit patterns were reviewed; none was consumed.

### Pattern screen

lane_echo: persistence, commands, events, transactions, world graph, and integration were screened;
this change is isolated to the native XLSX parser and its hostile-input fixture.

catalogue_match: no exact Certified Tier or Working Shelf Part matched bounded XML token scanning;
adjacent hostile-input patterns were not drop-in implementations.

recurrence_check: hostile-input refusal and generated-artifact/toolchain state recur in this branch;
the nested XML refusal is a new concrete parser boundary.

verdict_note: XML bomb fixture and parser refusal are proven; current-main reconciliation and full
gate are green. Ready for independent review, not self-certified for merge.

### Reusable Part signals

reimplemented: none observed; no existing Hardware Store Part covered XML nesting refusal.

recurrence: hostile-input refusal tests and generated-artifact preconditions recur across parser and
cross-language verification work.

generalizable: token-scan bounded XML element text before materializing values; pair parser limits
with a fixture beyond the limit and an `errors.Is` contract.

friction: the Windows patch helper required direct invocation because its batch wrapper dropped the
multiline patch terminator; the scratch/full-gate count differed by three passes and three skips.

### Boundary

`git diff --check` is clean. Current source changes are limited to `native/sheets/reader.go` and
`native/sheets/reader_test.go`; this report is the only additional path. No merge to main was
performed.
