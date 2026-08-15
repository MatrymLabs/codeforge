# WO-SL-01 Bench Report

packet_id: WO-SL-01
status: READY_FOR_VERIFICATION
branch: codex/wo-sl-01
repository: codeforge

## Summary

The SeedLab default Python command profiles now use `sys.executable`, so a build step runs with the
same interpreter as its spawning process. The `ruff` entry remains a bare executable because it is
not a Python interpreter and is resolved through the repository's approved toolchain PATH.

## Files changed

- `kernel/seedlab/tool_runner.py`
- `tests/test_tool_runner.py`
- `work-orders/WO-SL-01/BENCH_REPORT.md`

No other profile, allowlist, gateway, or source file changed.

## Consume-first search

Certified Tier (`hardware-store-codex/catalog/`) was searched first for an interpreter-resolution,
same-process tool runner, and returned no candidate. Working Shelf (`codeforge/catalog/parts.yaml`)
was searched second. Its `controlled-tool-runner` entry is the authored runner itself and its
`safe-runner` entry governs allowlisting and shell-free execution, but neither supplies interpreter
resolution. No Part was consumed.

## Calibration before repair

The required gateway test was first run with `.venv/bin` removed from PATH. The sandbox initially
blocked socket creation, so the same command was rerun with socket access to reach the contract
failure:

```text
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:...
./.venv/bin/pytest --no-cov -q tests/test_gateway.py::test_live_master_client_workspace_flow_survives_gateway_restart

Build.Report {"seed":"LiveFlow","ok":false,"steps":[{"name":"pytest","status":"failed"}],...}
--- output ---
/usr/bin/python: No module named pytest
...
E       assert b"1 passed" in built.encode()
tests/test_gateway.py:1064: AssertionError
1 failed in 1.63s
exit 1
```

This is the required failure: the runner used the bare `python` and selected `/usr/bin/python`.

## Fix

`pytest`, `python-build`, and `python-version` now start with `sys.executable`. The profile test
asserts each Python entry uses the active interpreter and that no default profile begins with the
bare string `python`. `ruff` remains `ruff check .` because it is a non-Python tool and the bench
toolchain contract supplies its approved PATH location.

## Calibration after repair

The exact gateway test was rerun with `.venv/bin` still removed from PATH, with socket access:

```text
1 passed in 2.82s
exit 0
```

The same test was rerun with the normal PATH, including `.venv/bin`:

```text
1 passed in 2.33s
exit 0
```

The fix therefore passes both the machine-sensitive calibration and the ordinary environment.

## Proof Runs

```text
pytest --no-cov -q tests/test_tool_runner.py
18 passed in 1.64s
exit 0
```

```text
make proto
regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go
exit 0
```

Post-fix `make check` passed formatting, Ruff, import contracts, mypy (`824 source files`, no
errors), Rust and Go lint/type checks. Its unchanged full pytest phase reproduced the sandbox
socket failures around 33-44 percent and was interrupted with exit 130. The required gateway
calibration passed with socket access, and the runner twin is green.

## Scope checks

- Every Python entry in `DEFAULT_PROFILE` resolves through `sys.executable`.
- No default profile begins with bare `python`.
- `ruff` remains the only bare executable and is not a Python entry.
- The allowlist remains fixed and shell-free.
- `git diff --check` passed.

## Reusable Part signals

reimplemented: none observed; the existing same-interpreter rule was reused from
`kernel/shelf/console.py`, `kernel/seedlab/synthesis.py`, and `kernel/coupling.py`.
recurrence: this is another machine-sensitive gate in KF-S4-3's family: CI activated the venv and
hid the bare-interpreter defect, while a bench without inherited venv PATH exposed it.
generalizable: subprocess profiles that invoke Python should always use the spawning process's
absolute interpreter, while non-Python tools remain governed by the explicit toolchain PATH.
friction: socket access was required to reach the intended gateway calibration; without it the
sandbox failed earlier at server creation and masked the actual runner defect.

## Review

Principal Engineer Verification Duty should inspect the two-file source/test diff and rerun the
calibration with `.venv/bin` removed from PATH. No merge was performed.

IN PLAIN TERMS: SeedLab now runs Python build steps with the interpreter that launched it, so a bench no longer falls back to `/usr/bin/python` and loses pytest. The exact no-venv calibration and normal calibration both pass.
