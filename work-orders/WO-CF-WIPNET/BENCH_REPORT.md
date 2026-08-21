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
/b` reported no differences). Ruff then mechanically formatted three of the
four files for codeforge's repository-wide formatter; no logic or behavior was
changed. The scripts were not adapted for codeforge.

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

## Required proof run

`make wipnet && make check` was run with writable bench-local cache paths and
the uv-managed interpreter. WIPNET succeeded, then codeforge's gate stopped at
Ruff:

```text
1167 files already formatted
Found 22 errors.
No fixes available (1 hidden fix can be enabled with the --unsafe-fixes option).
make: *** [Makefile:115: lint-python] Error 1
```

The findings are in the copied Ship instruments/tests: subprocess security
rules (`S603`, `S607`), complexity/style rules (`PLR2004`, `PLR0911`), and
`RUF015`. The work order explicitly forbids adapting the scripts, while its
allowlist forbids changing codeforge's Ruff policy. Therefore this bench cannot
honestly claim a green `make check` without a separate ruling that resolves
that scope conflict.

status: BLOCKED_BY_REPOSITORY_LINT_POLICY
