# Bench Report: WO-CACHE-SCOPE-1

## Result

Ruff and mypy are CLEAN across `codeforge-codex` and `codeforge-claude`. The shared
name-scoped cache paths remain unchanged. No `.gitignore` change was needed.

The two repositories agree, so there is no cross-repository discrepancy to escalate.

## Experiment transcript

Tree A was `codeforge-codex`. The probes were throwaway files and were deleted before the
tree-B runs.

Ruff tree A:

```text
F401 [*] `os` imported but unused
 --> cache_scope_ruff_probe.py:1:8
  |
1 | import os
  |        ^^
help: Remove unused import: `os`
  |
  - import os
  |

Found 1 error.
[*] 1 fixable with the `--fix` option.
RUFF_A_EXIT=1
```

mypy tree A:

```text
cache_scope_mypy_probe.py:2: error: Incompatible return value type (got "str", expected "int") [return-value]
Found 1 error in 1 file (checked 1 source file)
MYPY_A_EXIT=1
```

Removal was verified:

```text
Success. Updated the following files:
D cache_scope_ruff_probe.py
D cache_scope_mypy_probe.py
RUFF_PROBE_EXISTS=False
MYPY_PROBE_EXISTS=False
```

Tree B was `codeforge-claude`, with the same cache directories and no probe files.

Ruff tree B:

```text
All checks passed!
RUFF_B_EXIT=0
```

mypy tree B:

```text
Success: no issues found in 405 source files
MYPY_B_EXIT=0
```

Neither tree-B result named the deleted tree-A path or finding. Verdict: CLEAN for both tools.

## Measured mechanism

The Ruff cache records inspected on disk begin with the absolute source path, including the
checkout directory. The mypy cache is SQLite with a `files2(path, mtime, data)` table; the
deleted probe's metadata retained `cache_scope_mypy_probe.py`, the source/options hash, and the
error data, but the tree-B run did not load it because the source was absent. These mechanisms
make the shared cache safe for this two-checkout arrangement.

The Makefile now records this measured exemption directly above the unchanged cache variables.

## Proof run

Command executed directly, without a pipe:

```text
GOFLAGS=-buildvcs=false make check; echo $?
```

PowerShell equivalent used to preserve the environment variable and print the native exit code:

```text
ruff format --check .
1158 files already formatted
ruff check .
All checks passed!
Success: no issues found in 405 source files
5432 passed, 57 skipped, 1 xfailed in 55.10s
Required test coverage of 85% reached. Total coverage: 93.36%
MAKE_CHECK_EXIT=0
```

Post-report rerun: `make check` completed with `1159 files already formatted`, the same 5432
passed, 57 skipped, 1 xfailed result, and `MAKE_CHECK_EXIT=0`.

## Pattern screen

- Lane echo: configuration and gate behavior only; no persistence, commands, events,
  transactions, world graph, or integration change observed.
- Catalogue match: no existing reusable Part for cross-checkout cache isolation was found in
  the Certified Tier or Working Shelf.
- Recurrence: this is the second repository-level cache-isolation investigation after the
  golangci-lint incident, but the tools' measured path and content validation are the relevant
  mechanism here.
- Verdict: retain the shared name-scoped cache paths and preserve the evidence comment.

## Extraction signals

reimplemented: "None observed. This order measured tool behavior and recorded the result; it did
not reimplement cache logic."

recurrence: "Cache isolation is a recurring gate concern, but Ruff and mypy already provide the
required isolation mechanisms. No new implementation pattern was authored."

generalizable: "The two-tree planted-violation experiment is reusable for checking whether a
name-scoped tool cache is safe before changing cache configuration."

friction: "The sibling-tree test must use the repository's actual Makefile target. A bare `mypy`
invocation has no target in ship, while codeforge's target supplies its configured scope."

## IN PLAIN TERMS

I planted one Ruff error and one mypy type error in codeforge-codex, proved each tool reported it,
deleted both files, and ran the sibling checkout. The sibling reported neither old error. Ruff
stores absolute source paths; mypy checks the source filename and hash. The shared cache paths are
safe, so they were left alone and the reason is now written beside them.
