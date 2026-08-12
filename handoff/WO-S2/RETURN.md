# RETURN WO-S2

packet_id: WO-S2
pr_url: https://github.com/MatrymLabs/codeforge/pull/929
status: COMPLETE
tests_passing: yes

## Commands run

### Preconditions and consume-first search

```text
190:@app.websocket("/ws")
98:class Engine2DStub:
kernel/shelf/contract.py exists
Certified Tier: 7 CARD.md files searched for wire, schema, and envelope; no matching Part found.
Working Shelf: Validated Loader (catalog/parts.yaml:50), Typed API Contract
(catalog/parts.yaml:172), and Contract Jig (catalog/parts.yaml:1517) inspected.
```

`kernel/seam/` contained ignored bytecode only (`__pycache__/__init__.cpython-313.pyc` and
`__pycache__/wire.cpython-313.pyc`), so the filesystem-absence check returned 1. No tracked
source existed there and the allowlisted source package was created without deleting the residue.

Contract Jig is consumed in place through `Contract` and `verify`. Typed API Contract is not used:
it defines Pydantic/OpenAPI HTTP edge contracts, while this packet defines a small WebSocket frame
schema. Validated Loader is not used: it validates seeded YAML during loading, not network frames.

### Targeted protocol tests

```text
............
```

### Required verification command, after the implementation

```text
$ export PATH="$PWD/.venv/bin:$PATH" && make check
ruff format --check .
1072 files already formatted
ruff check .
All checks passed!
lint-rust: native/codeforge_nav
   Compiling target-lexicon v0.13.5
   Compiling proc-macro2 v1.0.107
   Compiling quote v1.0.47
   Compiling unicode-ident v1.0.24
   Compiling libc v0.2.189
   Compiling heck v0.5.0
    Checking once_cell v1.21.4
   Compiling pyo3-build-config v0.29.0
   Compiling syn v2.0.119
   Compiling pyo3-ffi v0.29.0
   Compiling pyo3 v0.29.0
   Compiling pyo3-macros-backend v0.29.0
   Compiling pyo3-macros v0.29.0
    Checking codeforge_nav v0.1.0 (/home/josh/Projects/MatrymLabs/codeforge-codex/native/codeforge_nav)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 25.75s
lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
          run `make proto` (ADR-0012: the bindings are git-ignored).
make: *** [Makefile:61: lint-go] Error 1
```

### Prescribed environment setup

```text
$ export PATH="$PWD/.venv/bin:$PATH" && make proto
protoc --proto_path=proto --python_out=proto proto/telemetry.proto
protoc --proto_path=proto --go_out=native/spine --go_opt=module=codeforge/spine proto/telemetry.proto
protoc-gen-go: program not found or is not executable
Please specify a program using absolute path or make sure the program is available in your PATH system variable
--go_out: protoc-gen-go: Plugin failed with status code 1.
make: *** [Makefile:333: proto] Error 1
```

### Current base and changed paths

```text
$ git rev-list --count HEAD..origin/main
0

$ git diff --cached --stat
 adapters/web_gateway.py            |  36 ++++++++++
 handoff/WO-S2/RETURN.md            | 136 +++++++++++++++++++++++++++++++++++++
 kernel/seam/__init__.py            |   1 +
 kernel/seam/wire.py                | 105 ++++++++++++++++++++++++++++
 registry/designations/modules.json |  29 ++++++++
 tests/test_wire_protocol.py        |  90 ++++++++++++++++++++++++
 6 files changed, 397 insertions(+)

$ git diff --cached --name-only
adapters/web_gateway.py
handoff/WO-S2/RETURN.md
kernel/seam/__init__.py
kernel/seam/wire.py
registry/designations/modules.json
tests/test_wire_protocol.py
```

Every changed path is allowlisted. `.venv/` is a pre-existing untracked local environment.

## Verification update

The original Go-toolchain blocker is resolved. With the requested environment:

```text
$ export PATH="$HOME/.local/go/bin:$HOME/go/bin:$PWD/.venv/bin:$PATH"
$ make proto
regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go
```

The language, import, typecheck, and exit-integrity stages passed. The complete gate is NOT green:
coverage reached 57% with test errors and failures, then the bounded run timed out at 300 seconds:

```text
lint-go: native/edge
0 issues.
lint-go: native/spine
0 issues.
Contracts: 4 kept, 0 broken.
Success: no issues found in 810 source files
typecheck-go: native/edge
typecheck-go: native/spine
Declared one-way exits:
- cellar --west--> workshop
- workshop --down--> cellar
pytest -n auto --cov=kernel --cov=adapters --cov=content --cov=forge --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=85
4 workers [5264 items]
......................................E.....................EEEEEEEEE... [ 34%]
...............................F......
................................make: *** [Makefile:250: coverage] Terminated
```

The command was run as `timeout 300s make check` after `make proto`; its exit status was `124`.
The packet remains `BLOCKED` until the full gate completes with zero failures and the required
coverage threshold.

The gate also generated `native/edge/edge`; it was moved to `/tmp/codeforge-edge-gate-artifact` and
is not part of the branch.

## Resume verification

`make proto` succeeded after exposing the existing `/home/josh/go/bin/protoc-gen-go`, but the whole
gate remained blocked:

```text
ruff format --check .
1073 files already formatted
ruff check .
All checks passed!
lint-rust: native/codeforge_nav
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 13.75s
lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
          run `make proto` (ADR-0012: the bindings are git-ignored).
make: *** [Makefile:61: lint-go] Error 1
```

The direct diagnostic confirms the environmental blocker:

```text
$ (cd native/edge && go build ./...)
/bin/bash: line 1: go: command not found
```

`gh pr view 929` reports the PR OPEN and merge state BLOCKED. No source workaround was attempted.

## Contract coverage finding

The wire schema defines four message kinds: `hello`, `move_intent`, `entity_state`, and `tick`.
Only `hello` is currently registered in `CLIENT_CONTRACTS`, so provider-side Contract Jig coverage
is **1 of 4 message kinds (25%)**. This order's contract test proves the hello field-drop refusal;
contracts for the other three kinds belong in a follow-on packet.

## Outside-order rulings requested

1. Open a follow-on packet for `/ws/engine-2d` connection policy, including authentication,
   lifecycle, refusal, and close semantics. This order intentionally implements only the versioned
   hello handshake.
2. Open a follow-on packet for provider-side contracts covering `entity_state`, `move_intent`, and
   `tick`, closing the 1-of-4 coverage gap.
3. File a separate repository-hygiene packet for the gate's generated `native/edge/edge` artifact:
   `Makefile:65` and `Makefile:89` build that filename, while `.gitignore:57` ignores the different
   `native/edge/codeforge-edge` name. This is outside WO-S2's allowlist and is not changed here.

## Extraction signals

reimplemented: none observed. Contract Jig was consumed in place rather than copied.

recurrence: first occurrence in this repository of a versioned Engine-2D WebSocket schema backed by
a provider-side consumer contract.

generalizable: the versioned-frame validation and provider-side contract shape could serve another
network client only after a second real consumer exists.

friction: Contract Jig is Python-only, so the future GDScript client cannot declare the contract
itself. The Python contract is an honest server-side guarantee against dropped or retyped declared
fields, but it relocates the consumer-authorship problem until the Godot client supplies an
equivalent declared read set.

dissent: none. The packet's sibling-route decision preserved the browser demo gate and the command
door boundary.

pattern_shapes: versioned protocol decoder, explicit refusal frame, consumer-driven provider
contract, and single-message WebSocket handshake.

## Pattern screen

lane_echo: none observed in persistence, commands, events, transactions, world graph, or
integration beyond the consumed Contract Jig.

catalogue_match: Contract Jig, `catalog/parts.yaml:1517`, consumed in place. No Certified Tier
card matches a wire, schema, or envelope capability.

recurrence_check: none observed. This is the first named consumer of this wire-schema shape.

verdict_note: Contract Jig consumption is recorded. The Python-on-behalf-of-GDScript limitation is
flagged as coordination friction, not extracted before a second consumer exists.

## Merge verification correction

The authoritative verification for merged commit `09decacb65791823e703d3b0cdaf3e9050c284a5` was
CI run [31638154665](https://github.com/MatrymLabs/codeforge/actions/runs/31638154665):

```text
check: SUCCESS
postgres: SUCCESS
e2e: SUCCESS
docker: SUCCESS
terraform: SUCCESS
native: SUCCESS
go-edge: SUCCESS
spine: SUCCESS
c-kernel: SUCCESS
lua: SUCCESS
shelf-drift: SUCCESS
```

`make proto` also passed this session after exposing `protoc-gen-go`. The local full-gate rerun
reached pytest but was not reproducible on this host because of read-only Go caches and test-worker
failures; those failures are retained as evidence rather than hidden. The merged CI run is the
passing verification for the merged commit. `git rev-list --count HEAD..origin/main` returned `0`.

Contract coverage is **1 of 4 message kinds (25%)**. The merged change added four tests protecting
the dropped-field criterion, which had previously been unprotected. Contracts for `entity_state`,
`move_intent`, and `tick` remain a follow-on order.
