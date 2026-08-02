"""Benchmark: the C text kernel vs the pure-Python reference on edit distance.

Evidence for the lowest-level organ -- the O(m*n) edit-distance DP is cheap in C, slow in a Python
loop, with no stdlib shortcut. Times many distance calls over medium-length strings on each backend,
and a realistic "did you mean" (closest word over a vocabulary). Frameless (perf_counter based).
Run: `python benchmarks/bench_textmatch.py [n_pairs]`.

If the C kernel is not built it reports the Python numbers alone (no speedup line); it still runs.
"""

from __future__ import annotations

import random
import statistics
import sys
import time
from collections.abc import Callable

from kernel.shelf.textmatch import TEXTMATCH_BACKEND, closest, levenshtein_py

try:  # the C kernel, if built
    import codeforge_textkernel

    _c_levenshtein: Callable[[str, str], int] | None = codeforge_textkernel.levenshtein
except ImportError:
    _c_levenshtein = None


def _words(n: int, length: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    letters = "abcdefghijklmnopqrstuvwxyz"
    return ["".join(rng.choice(letters) for _ in range(length)) for _ in range(n)]


def _median_ms(fn: Callable[[], object], runs: int = 5) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
    left = _words(n, 12, seed=1)
    right = _words(n, 12, seed=2)
    pairs = list(zip(left, right, strict=True))
    vocabulary = _words(300, 8, seed=3)
    queries = _words(500, 8, seed=4)

    print(f"text kernel benchmark -- {n:,} distance pairs (len 12), backend={TEXTMATCH_BACKEND}\n")

    def py_distances() -> None:
        for a, b in pairs:
            levenshtein_py(a, b)

    py_ms = _median_ms(py_distances)
    line = f"  {'distance x' + f'{n:,}':>16}   python {py_ms:>9.2f} ms"
    if _c_levenshtein is not None:

        def c_distances() -> None:
            for a, b in pairs:
                _c_levenshtein(a, b)

        c_ms = _median_ms(c_distances)
        line += f"   c {c_ms:>8.2f} ms   ({py_ms / c_ms:>5.1f}x)"
    print(line)

    # a realistic "did you mean": nearest vocabulary word for each query (uses the active backend)
    closest_ms = _median_ms(lambda: [closest(q, vocabulary, max_distance=3) for q in queries])
    print(
        f"  {'closest x500/300':>16}   active {closest_ms:>9.2f} ms  (backend {TEXTMATCH_BACKEND})"
    )

    if _c_levenshtein is None:
        print("\n(C kernel not built -- Python numbers only; pip install ./native/textkernel)")


if __name__ == "__main__":
    main()
