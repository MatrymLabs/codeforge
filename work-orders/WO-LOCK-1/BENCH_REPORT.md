# WO-LOCK-1B Bench Report

## Change

On a fresh branch from current `origin/main` (`53660e06`), the `env` target now
uses the existing lockfile:

```text
uv sync --locked --extra dev --python 3.13
```

No `uv.lock` change was made.

## Lock break proof

The break test was independently reproduced by the dispatching bench before this
landing order. The manifest was changed without updating `uv.lock`:

```text
uv sync --locked
exit 1
error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.
```

After restoring the manifest:

```text
uv sync --locked
exit 0
```

This demonstrates that the new mode rejects manifest/lock drift rather than
silently resolving a new lock.

## Proof run

`make check` was run on this Windows bench. The first unmodified run reached the
Go gate and stopped with the repository's explicit cache diagnostic:

```text
lint-go: UNVERIFIED - the Go build cache is not writable: C:\Users\jevan\AppData\Local\go-build
make: *** [Makefile:230: lint-go] Error 1
```

The retry used a writable repository-local `GOCACHE` and `GOFLAGS=-buildvcs=false`
to remove the bench's cache and native VCS-stamping faults. Go lint then passed,
but the next native gate failed:

```text
lint-go: native/edge
0 issues.
lint-go: native/sheets
0 issues.
lint-go: native/spine
0 issues.
lint-terraform: deploy/terraform
did not find executable at 'C:\Users\jevan\AppData\Local\Programs\Python\Python313\python.exe': Access is denied.
lint-c: native/textkernel/src/textkernel.c  [gcc]
gcc.exe: fatal error: no input files
compilation terminated.
make: *** [Makefile:152: lint-c] Error 1
```

A separate serialized run reached pytest with 32/32 workers and 5,497 collected
items, but the sandbox run lost workers and did not produce a valid completion
summary. Its exact worker failure was:

```text
[gw31] node down: Not properly terminated
replacing crashed worker gw31
[gw30] node down: Not properly terminated
replacing crashed worker gw30
OSError: [Errno 22] Invalid argument
```

Therefore this bench does not claim a green local `make check`; the failures are
environmental/native-runner evidence and are preserved for CI verification.

status: READY_FOR_CI
