# Evidence: the first real synthesis run

date: 2026-08-08
packet: P-07
verdict: **verified**
run by: Josh (founder), local shell, live API

## What this proves

A live `claude-opus-5` implementer generated working business logic from a behavioral spec and
passed the spec-derived tests **on the first iteration**. The fabrication pipeline emits logic, not
scaffolding.

This retires the oldest caveat in `MATRYM_NORTH_STAR.md` section 7, which read
"business-logic generation (scaffolds, not logic)". That statement was true when written and is no
longer true. The correction is recorded here rather than asserted in the doc.

## What this does NOT prove

**`mutation_score: None` - the mutation gate did not run.** `MutationScorer` is a Protocol in
`kernel/seedlab/synthesis.py` with no real implementation; the only implementation in the repo is
`_FixedScorer` in `tests/test_synthesis.py`, a fake. So this run shows the model produced code that
passes the spec tests. It does NOT show those tests bite hard enough to catch a subtle defect.

That gap is real and is filed separately. Do not read this artifact as a mutation-verified result.

Scope is also small by design: one spec, two acceptance cases, one iteration. This is the first true
data point, not a capability claim.

## Why the result is not self-affirming

`adapters/synthesis_ai.py` drops any generated file whose path matches a spec test:

```python
source = {f.path: f.content for f in generated.files if f.path not in tests}
```

The model could not see, edit, or replace the tests it was judged against. It received a goal and had
to produce source that independently satisfies tests derived from the spec.

## The run

```
model:           claude-opus-5   (max_tokens=16000, thinking on by default)
spec:            ProjectModel(identity="greet")
cases:           ("--name","Josh") -> "Hello, Josh!\n"
                 ()                -> "Hello, world!\n"
scorer:          None (no real implementation exists)
max_iterations:  3 (default)

verdict:         verified
iterations:      1
exit_code:       0
test output:     2 passed in 0.17s
duration:        0.61s (test run); whole loop ~1 model call
mutation_score:  None
when:            2026-08-08T18:29:02Z
```

## The spec-derived tests (written by the harness, not the model)

```python
from cli import main

def test_case_0(capsys):
    code = main(["--name", "Josh"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "Hello, Josh!\n"


def test_case_1(capsys):
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "Hello, world!\n"
```

## The generated source

Reproduced byte-for-byte, unformatted. `ruff format` would collapse one `raise` onto a single
line; that edit is not applied, because a formatter must never rewrite a record. `docs/evidence/`
is excluded from ruff in `pyproject.toml` for exactly this reason.

```python
"""Minimal greeting CLI.

Usage:
    python cli.py [--name NAME]
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

DEFAULT_NAME = "world"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greet",
        description="Print a friendly greeting.",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help="name to greet (default: %(default)s)",
    )
    return parser


def greeting(name: str) -> str:
    """Return the greeting line for *name*.

    Raises TypeError if *name* is not a string.
    """
    if not isinstance(name, str):
        raise TypeError(f"name must be a str, got {type(name).__name__}")
    cleaned = name.strip()
    if not cleaned:
        cleaned = DEFAULT_NAME
    return f"Hello, {cleaned}!"


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    else:
        if isinstance(argv, (str, bytes)):
            raise TypeError("argv must be a sequence of strings, not a string")
        args_list: List[str] = list(argv)
        for item in args_list:
            if not isinstance(item, str):
                raise TypeError(
                    f"argv entries must be str, got {type(item).__name__}"
                )
        argv = args_list

    parser = build_parser()
    args = parser.parse_args(argv)
    print(greeting(args.name))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

## Observation worth recording

The spec asked only for two stdout strings. The model went further on its own: it extracted
`DEFAULT_NAME` as a constant, split `greeting()` out as a pure function, added a `strip()`-then-
fallback so `--name "   "` still greets the world, and added `TypeError` guards on `argv`. None of
that was requested. That is judgment, not pattern completion - and it is also the over-engineering
tendency the claude-api guidance warns about for this model. Worth watching on larger specs.

## Follow-up

1. **Write a real `MutationScorer`** backed by cosmic-ray, then re-run this spec with the gate on.
   Until then no synthesis result in this repo is mutation-verified.
2. Re-run at larger spec sizes to see where `RED_BUDGET_EXHAUSTED` starts appearing.
