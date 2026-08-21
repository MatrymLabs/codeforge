# Bench Report: WO-ENV-PIN

```yaml
packet_id: WO-ENV-PIN
status: COMPLETE
branch: codex/wo-env-pin
pr_url: https://github.com/MatrymLabs/codeforge/pull/1065
allowlist:
  - Makefile
  - work-orders/WO-ENV-PIN/BENCH_REPORT.md
```

## Summary

The fallback previously selected `python3` without checking its version. On this Windows bench,
that resolved to Python 3.14.0 while the uv path was pinned to Python 3.13.12. The Makefile now
selects a system candidate whose major.minor is exactly 3.13 and prints the selected venv
interpreter before asserting the pin.

## Consume-First Search

Read first: `C:\Projects\MatrymLabs\ship-codex-bench\Makefile`, including its `PY ?=` chain and
the KF-WIN-1 comment explaining why `python` precedes `python3` on Windows. That existing rule
solves executable existence; this order required version identity, so it was not copied unchanged.

## Failure Before Repair

Measured system candidates:

```text
python  -> 3.13.12
python3 -> 3.14.0
```

With no `.venv`, the pre-repair fallback selected `python3` and produced:

```text
Python 3.14.0
```

The prescribed uv break fixture was independently reproduced:

```text
UV_CACHE_DIR=C:\Users\jevan\AppData\Local\Temp\wo-env-pin-cache-file-20260821
uv sync --locked --extra dev --python 3.13
error: Failed to initialize cache at `C:\Users\jevan\AppData\Local\Temp\wo-env-pin-cache-file-20260821`
  Caused by: failed to create directory ... Cannot create a file when that file already exists. (os error 183)
EXIT 2
```

## Change

`Makefile` now checks, in order:

1. an existing Windows venv;
2. an existing POSIX venv;
3. `python3.13`;
4. `python` only when it reports 3.13;
5. `python3` only when it reports 3.13;
6. the final version assertion refuses anything else.

The common validation line prints the executable and major.minor, then asserts exactly Python
3.13. This makes uv and fallback selection observable.

## Proof Runs

Normal uv path, after repair:

```text
make env
Using CPython 3.13.14
-> uv env built (pinned from uv.lock)
venv interpreter: C:\Projects\MatrymLabs\codeforge-codex\.venv\Scripts\python.exe (3.13)
venv ready - activate with: source .venv/Scripts/activate

uv-built venv: Python 3.13.14
```

Forced fallback path, with the file-valued `UV_CACHE_DIR` break fixture:

```text
make env
error: Failed to initialize cache at `C:\Users\jevan\AppData\Local\Temp\wo-env-pin-cache-file-20260821`
-> uv unavailable or failed; building with venv + pip.
venv interpreter: C:\Projects\MatrymLabs\codeforge-codex\.venv\Scripts\python.exe (3.13)
venv ready - activate with: source .venv/Scripts/activate
EXIT 0

fallback venv: Python 3.13.14
```

The fallback venv imported the CodeForge kernel:

```text
KERNEL_IMPORT_OK
```

## Known Environment Noise

The fallback emitted pip's self-upgrade notice and, on one rerun over an existing venv, a uv
launcher-copy warning. The target still exited 0 and the fresh fallback interpreter was 3.13.
No unrelated repair was made.

## Reusable Part Signals

reimplemented: none observed; consumed Ship's version-aware interpreter-selection pattern
recurrence: bootstrap interpreter drift recurs at the Windows `python`/`python3` boundary
generalizable: select a candidate by executable version, then print the selected executable and version before asserting
friction: uv cache failure was initially difficult to inject through the shell; an explicit subprocess environment was required

## Pattern Screen

lane_echo: none observed; this was Makefile bootstrap logic, not another agent's runtime diff
catalogue_match: none observed
recurrence_check: interpreter selection is a second occurrence of host-tool resolution drift
verdict_note: no new Part authored; the existing Ship pattern was consumed and narrowed to the version invariant

## Result

COMPLETE. The uv and forced-fallback paths both produce Python 3.13 and print which interpreter
was used. Ready for independent review.
