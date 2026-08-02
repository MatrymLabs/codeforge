# codeforge_textkernel (C)

A hand-written CPython extension using the **raw Python/C API** -- no PyO3, no pybind11, no Cython.
The lowest-level polyglot organ: `PyObject` arguments parsed by hand, a scratch row managed with
`PyMem`, code points read with the Unicode API, and an `int` built back for Python.

## What it does

One hot primitive: `levenshtein(a, b) -> int`, the edit distance between two strings. The O(m*n)
dynamic program is cheap in C and slow in a Python loop, and there is **no stdlib shortcut** for it --
exactly the shape where hand-written C earns its place. It powers fuzzy matching: the "command not
found -- did you mean ...?" nudge in the engine tick, via `kernel/shelf/textmatch.py`.

## Optional (ADR-0010)

This module is an accelerator. When it is not built, `kernel.shelf.textmatch` runs the identical
pure-Python `levenshtein_py` and the game is unaffected; a parity test pins the two equal and a
benchmark records the speedup. Nothing in the game hard-depends on a C toolchain.

## Build

```sh
pip install ./native/textkernel      # from the repo root (the c-kernel CI job does exactly this)
```

Build artifacts are git-ignored. Needs a C compiler and the Python dev headers (`Python.h`).

## Test / benchmark

- Parity + closest(): `pytest tests/test_textmatch.py` (a hypothesis property test pins the C kernel
  to the Python reference over random text when built).
- Speedup: `python benchmarks/bench_textmatch.py`. Measured on the Pi (2026-07-28): **~53x** faster
  than the Python reference on 20k distance pairs (10.9 ms vs 573 ms).
