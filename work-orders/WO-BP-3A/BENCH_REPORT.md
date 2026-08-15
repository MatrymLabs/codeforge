# WO-BP-3A Bench Report

```yaml
packet_id: WO-BP-3A
title: SeedError -> BlueprintError
repository: codeforge
stream: engine
taint_class: SAFE
status: READY_FOR_REVIEW
branch: codex/wo-bp-3a
base: origin/main
```

## Summary

Renamed the internal `SeedError` identifier to `BlueprintError` across the 46 CodeForge Python
files that used it. `kernel/world/seed.py` retains one deliberate module-boundary compatibility
alias, and tests assert both that the alias works and that no other Python occurrence remains.

No frozen contract was changed: content paths, environment variables, CLI flags, YAML keys,
database columns, and CLI verbs were untouched.

## Preconditions and boundary checks

`CMD: git rev-list --count HEAD..origin/main`

```text
0
```

`CMD: git grep -nE 'SeedError|BlueprintError' origin/main -- '*.py'`

Origin contains `BlueprintError` in `kernel/blueprint.py` and the BP-1 compatibility tests for
the Blueprint and Seed spellings. The legacy world-loader class is still present on origin, which
is the subject of this order. The BP-1 equivalence and precedence tests pass on the current branch.

`CMD: git grep -l 'SeedError' origin/main -- '*.py' | wc -l`

```text
46
```

`CMD: external consumer scan`

The CodeForge client, console, shelf mirror, and local hardware-store mirror contained no imports
of CodeForge's `kernel.world.seed` exception. The CodeForge client's own parser exception with the
same spelling is independent code and was not touched.

## Consume-first search

`CMD: grep -RniE 'error taxonomy|exception naming|compatibility alias|rename|backward compatibility|backwards compatibility|symbol alias' hardware-store-codex/catalog`

No reusable Part matched. The only hits were an unrelated typed-settings test comment and an
atomic-file rename Part.

`CMD: grep -niE 'error taxonomy|exception naming|compatibility alias|rename|backward compatibility|backwards compatibility|symbol alias' catalog/parts.yaml`

No reusable Part matched. No Part was consumed or reimplemented. This search was performed after
the mechanical implementation rather than before it; that process miss is recorded under
friction rather than hidden.

## Failure before repair

The count lock was added before the rename and run immediately:

`CMD: .venv/bin/pytest -q tests/test_seed.py::test_blueprint_error_is_the_only_legacy_error_spelling`

```text
FAILED
E       assert len(occurrences) == 1, occurrences
E       assert 421 == 1
1 failed in 0.99s
exit 1
```

The first repository proof after the rename exposed formatting drift:

`CMD: export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH" && make proto && make check`

```text
unformatted: File would be reformatted
9 files would be reformatted, 1108 files already formatted
make: *** [Makefile:50: lint-python] Error 1
exit 2
```

After formatting, the same proof exposed 18 Ruff errors, consisting of 11 import-order fixes and
7 line-length fixes caused by the longer identifier. Ruff repaired only the claimed files, and the
proof was run again.

## Changes

- Renamed the class and all internal references to `BlueprintError` in the 46 measured Python files.
- Added `SeedError = BlueprintError` in `kernel/world/seed.py` as the sole compatibility alias.
- Added a test that counts the legacy spelling across repository Python files and requires exactly
  the deliberate alias.
- Added a test that resolves the legacy module attribute dynamically and requires it to be the new
  exception class.
- Updated only formatting and import ordering required by the identifier length and spelling.

## Proof Runs

`CMD: .venv/bin/pytest -q <27 affected test files>`

```text
776 passed in 29.20s
exit 0
```

`CMD: .venv/bin/pytest -q tests/test_seed.py::test_blueprint_error_is_the_only_legacy_error_spelling tests/test_seed.py::test_legacy_error_alias_preserves_the_module_boundary`

```text
2 passed in 1.52s
exit 0
```

`CMD: git grep -n 'SeedError' -- '*.py'`

```text
kernel/world/seed.py:451:SeedError = BlueprintError
```

`CMD: git grep -l 'SeedError' -- '*.py' | wc -l`

```text
1
```

`CMD: git rev-list --count HEAD..origin/main`

```text
0
```

`CMD: export PATH="$PWD/.venv/bin:$HOME/.local/go/bin:$HOME/go/bin:$HOME/.cargo/bin:$HOME/.local/bin:$PATH" && make proto && make check`

```text
1117 files already formatted
All checks passed!
Contracts: 4 kept, 0 broken.
Success: no issues found in 826 source files
Required test coverage of 85% reached. Total coverage: 93.46%
5307 passed, 54 skipped, 74 warnings in 239.13s
exit 0
```

The canonical proof first stalled in the sandbox during the final secret scan and was interrupted
with exit 130. The same command was then rerun with approved escalated execution and completed with
exit 0. The scanner output contained warnings only, with no findings.

`CMD: git diff --check`

```text
exit 0
```

## Scope

The CodeForge diff contains the 46 measured Python files and this Bench Report only. No client,
console, shelf mirror, content, database, environment, CLI contract, or generated tracked file was
changed.

## Pattern and extraction signals

```yaml
pattern_shapes: >
  A repository-wide identifier migration with one module-boundary compatibility alias and a count
  lock that makes the permitted legacy surface explicit.
reimplemented: none observed; no matching Hardware Store Part existed in either tier.
recurrence: none observed as a second reusable Part consumer; this is one error-class boundary.
generalizable: >
  A staged internal rename can preserve external callers with one explicit module alias while all
  internal consumers move to the new name in the same commit.
friction: >
  The Certified and Working Shelf searches were performed after implementation, a process miss.
  The first local full check also stalled in the secret scanner; escalated execution completed it.
```

## Principal Engineer review

Please verify the fresh `make proto && make check`, inspect that the one remaining legacy occurrence
is intentional, and confirm the external boundary scan before merge. No merge was performed by
Codex.

## IN PLAIN TERMS

The code now calls this validation failure a Blueprint error everywhere inside CodeForge, while old
imports still work through one compatibility alias. This keeps the rename safe for the M2 engine
while making the new Blueprint vocabulary real in the implementation. The key concept is a
compatibility alias: one old doorway stays open while the building is renamed inside.
