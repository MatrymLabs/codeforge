# WO-BP-4 Bench Report

packet_id: WO-BP-4
status: READY_FOR_VERIFICATION
branch: codex/wo-bp-4
repository: codeforge

## Summary

The unique Blueprint YAML mapping constructor now turns unhashable mapping and sequence keys into
an actionable `SeedError`. Duplicate scalar-key detection is unchanged. The two parked Hypothesis
database entries are committed under `tests/corpora/` byte-identically.

## Failure observed before repair

The required reproduction ran on `origin/main` before any source, test, report, or corpus edit:

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import yaml; from kernel.world.seed import _UniqueKeyLoader; yaml.load('? ?', Loader=_UniqueKeyLoader)
                                                                 ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/__init__.py", line 81, in load
    return loader.get_single_data()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/constructor.py", line 51, in get_single_data
    return self.construct_document(node)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/constructor.py", line 55, in construct_document
    data = self.construct_object(node)
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/constructor.py", line 100, in construct_object
    data = constructor(self, node)
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/kernel/world/seed.py", line 469, in _construct_unique_mapping
    if key in mapping:
       ^^^^^^^^^^^^^^
TypeError: unhashable type: 'dict'
```

## Files changed

- `kernel/world/seed.py`
- `tests/test_seed.py`
- `tests/corpora/04e6b3400353b141/763eb9e4fba210c0`
- `tests/corpora/763eb9e4fba210c0/3d7f9789eaa78592`
- `work-orders/WO-BP-4/BENCH_REPORT.md`

`tests/test_fuzz_gates.py` was not changed.

## Fix and sibling case

The constructor catches the `TypeError` raised while checking an unhashable key and raises
`SeedError("Unusable key in Blueprint file ...")` instead. The loader does not receive a filename
when called with an in-memory YAML string, so the message names the Blueprint file generically.

The sibling sequence key `? [a]` has the same hashability fault and is covered by the new unit test;
both forms now produce `SeedError`.

## Corpus integrity

Both parked entries were copied into the committed Hypothesis database and compared with `cmp`.
Their SHA-256 values are:

```text
6312d87ecdbcd41de39f97c59b1057e3e4555906b112537b4236d6903db348ab  tests/corpora/04e6b3400353b141/763eb9e4fba210c0
6e2b86d5d28b562563e104f835bc16ac3d21f6ecaf54686cec8f3556d0c8ddc2  tests/corpora/763eb9e4fba210c0/3d7f9789eaa78592
```

The targeted fuzz run replayed these cases and Hypothesis removed them after the defect stopped
failing; they were restored from `/tmp/bp4-corpora` immediately before staging and the hashes above
were rechecked.

## Proof Runs

Post-fix reproduction:

```text
Traceback (most recent call last):
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/kernel/world/seed.py", line 470, in _construct_unique_mapping
    is_duplicate = key in mapping
                   ^^^^^^^^^^^^^
TypeError: unhashable type: 'dict'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import yaml; from kernel.world.seed import _UniqueKeyLoader; yaml.load('? ?', Loader=_UniqueKeyLoader)
                                                                 ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/__init__.py", line 81, in load
    return loader.get_single_data()
           ~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/constructor.py", line 51, in get_single_data
    return self.construct_document(node)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/constructor.py", line 55, in construct_document
    data = self.construct_object(node)
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/.venv/lib/python3.13/site-packages/yaml/constructor.py", line 100, in construct_object
    data = constructor(self, node)
  File "/home/josh/Projects/MatrymLabs/codeforge-codex/kernel/world/seed.py", line 472, in _construct_unique_mapping
    raise SeedError(
    ...<2 lines>...
    ) from exc
kernel.world.seed.SeedError: Unusable key in Blueprint file: {None: None} is not hashable. Keys must be scalar labels.
```

```text
pytest -q tests/test_seed.py tests/test_fuzz_gates.py
85 passed in 7.39s
exit 0
```

```text
make proto
regenerated proto/telemetry_pb2.py + native/spine/telemetrypb/telemetry.pb.go
exit 0
```

`make check` passed formatting, Ruff, Rust and Go lint, import contracts, mypy, and Rust and Go
type checks. Its full pytest phase reached the known network-sensitive sandbox failures around
65-67 percent and was interrupted with exit 130; it did not produce a clean full-suite verdict.

## Scope checks

- `tests/test_fuzz_gates.py` was not edited or weakened.
- `kernel/world/authored_towns.py` and `kernel/world/canon.py` were not edited.
- `kernel/world/seed.py` contains the only production change.
- `git diff --check` passed.
- `git diff --stat` contains only the allowlisted source, test, and required report; the two corpus
  entries are new tracked artifacts required by the order.

## Reusable Part signals

reimplemented: none observed; this fix uses the existing `SeedError` convention.
recurrence: this is the fifth wrong-cause failure report this week, after the four cases named in
the Build Sheet; the common pattern is infrastructure or validation failures escaping as a less
actionable cause.
generalizable: parser gates should convert lower-level type failures at the trust boundary into
the repository's typed, author-facing error before they reach a fuzz harness or caller.
friction: Hypothesis deletes passing database examples during replay, so corpus entries must be
restored and hash-checked immediately before staging; the sandbox also prevents a clean full-suite
pytest verdict because of network-sensitive tests.

## Review

Principal Engineer Verification Duty should rerun `make proto && make check`, the exact reproduction,
and inspect that the two corpus artifacts remain byte-identical. No merge or push was performed.

IN PLAIN TERMS: the two-character Blueprint crash now reports an unusable key as SeedError, the list-key sibling is covered too, and both fuzz pins are ready in the commit. The focused proof is green; full-suite verification still needs a non-isolated run.
