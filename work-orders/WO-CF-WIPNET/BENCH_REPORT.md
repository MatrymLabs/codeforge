# WO-CF-WIPNET Bench Report

## Port

Copied from Ship:

```text
scripts/wip_net.py
scripts/safe_take.py
scripts/test_wip_net.py
scripts/test_safe_take.py
```

The initial copies were byte-identical to the four Ship source/test twins (`fc
/b` reported no differences). Ruff then mechanically formatted the four files
for codeforge's repository-wide formatter; no logic or behavior was changed.
The scripts were not adapted for codeforge. To satisfy codeforge's stricter
lint policy without changing behavior, the port also names the status offset
and test constants, extracts the exposed-take branch to avoid a complexity
suppression, and adds 17 reasoned subprocess suppressions. Every suppression
explains why PATH-resolved `git` and the subprocess calls are intentional.

The Makefile adds `wipnet` and `take`, both invoking codeforge's `$(PY)`:

```text
wipnet:  $(PY) scripts/wip_net.py
take:    $(PY) scripts/safe_take.py --from ...
```

## Snapshot proof

The unqualified target exposes the existing stale venv:

```text
make wipnet
.venv/Scripts/python.exe scripts/wip_net.py
did not find executable at 'C:\Users\jevan\AppData\Local\Programs\Python\Python313\python.exe': Access is denied.
make: *** [Makefile:92: wipnet] Error 103
```

With the already-installed uv-managed Python supplied through `PY`, the target
ran and produced a snapshot without changing the working tree:

```text
make wipnet
WIPNET: snapshot 87c848329b9d20b25091d8e669e49dcdb28701ad
WIPNET: restore with `git checkout 87c848329b9d20b25091d8e669e49dcdb28701ad -- .`
```

## Refusal break test

The `safe_take.take` snapshotter was injected with a function that returns an
empty snapshot. The modified Makefile was the precious content at risk:

```text
SAFE-TAKE: REFUSED could not snapshot the working tree
SAFE-TAKE: 1 path(s) hold uncommitted content and were NOT touched:
    Makefile
SAFE-TAKE: commit, stash or copy them aside, then take again
RETURN 1
PRECIOUS_CONTENT_STILL_PRESENT True
UNCHANGED True
```

This proves the port refuses the take when its safety snapshot fails and leaves
the working content in place.

## Lint ruling and twin proof

The two copied test twins were run after each edit, then as complete files (17
tests total):

```text
scripts/test_wip_net.py: 4 passed, 1 warning
scripts/test_safe_take.py: 3 bridge tests passed, then 10 remaining tests passed
```

The required refusal test was rerun after the final edit:

```text
SAFE-TAKE: REFUSED could not snapshot the working tree
SAFE-TAKE: 1 path(s) hold uncommitted content and were NOT touched:
    tracked.txt
SAFE-TAKE: commit, stash or copy them aside, then take again
PASSED
1 passed, 1 warning in 1.51s
```

Targeted Ruff verification is green:

```text
ruff check scripts/wip_net.py scripts/safe_take.py scripts/test_wip_net.py scripts/test_safe_take.py
All checks passed!
ruff format --check scripts/wip_net.py scripts/safe_take.py scripts/test_wip_net.py scripts/test_safe_take.py
4 files already formatted
```

The suppression count was measured against `origin/main` before this change:
747 `# noqa` directives. This branch has 764, exactly +17. No `.ai/LEDGER.md`
exists in codeforge; the current tracked ledger row is outside the original
order allowlist and is called out here for the required ledger update.

## Required proof run

`make wipnet && make check` was rerun with the uv-managed interpreter and
writable bench-local cache paths. The WIPNET target and Python/Rust gates
passed. The exact environment findings were:

```text
first run: lint-go RED — Go VCS stamping resolved the outer C:\Projects\MatrymLabs
           repository and Git refused it: detected dubious ownership
second run with GOFLAGS=-buildvcs=false: Go edge/sheets/spine 0 issues; C and
           Terraform passed; imports RED — ModuleNotFoundError: No module named 'importlinter'
```

The full local `make check` is therefore not green on this bench because its
pre-existing Python environment lacks `importlinter`; CI remains the arbiter.

status: READY_FOR_CI
