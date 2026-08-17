"""Benchmark: the controlled runner (kernel/bench_control) proving itself on a real organ.

Demonstrates the new method end to end - pin a quiet core with the stdlib, run a seeded interleave,
and return an effect-size verdict that NAMES its conditions - on the C text kernel vs the
pure-Python reference (the organ bench_textmatch measures raw). Unlike the raw bench, this is honest
about whether the machine was actually controlled, and it runs the two backends INTERLEAVED so a
thermal drift under a busy host cannot systematically favour one. Frameless (perf_counter based).

Run: `python -m benchmarks.bench_controlled [n_pairs]`.
If the C kernel is not built it says so and exits (there is nothing to compare).
"""

from __future__ import annotations

import random
import sys

from kernel.bench_control import controlled_compare, quiet_core, render_controlled
from kernel.shelf.textmatch import levenshtein_py

try:
    import codeforge_textkernel

    _c_levenshtein = codeforge_textkernel.levenshtein
except ImportError:
    _c_levenshtein = None


def _pairs(n: int, length: int, seed: int) -> list[tuple[str, str]]:
    rng = random.Random(seed)  # noqa: S311
    letters = "abcdefghijklmnopqrstuvwxyz"

    def word() -> str:
        return "".join(rng.choice(letters) for _ in range(length))

    return [(word(), word()) for _ in range(n)]


def main() -> None:
    if _c_levenshtein is None:
        print("C text kernel not built - nothing to compare. Build it, then re-run.")
        return

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000
    pairs = _pairs(n, length=8, seed=1)

    def run_python() -> None:
        for a, b in pairs:
            levenshtein_py(a, b)

    def run_c() -> None:
        for a, b in pairs:
            _c_levenshtein(a, b)

    core = quiet_core()
    print(f"controlled bench: C text kernel vs pure-Python edit distance, {n} pairs/run")
    print(f"pinning to quiet core {core}; baseline=python, candidate=C\n")

    verdict, control = controlled_compare(
        run_python,  # baseline
        run_c,  # candidate
        repeats=15,
        warmup=3,
        seed=1,
        core=core,
    )
    print(render_controlled(verdict, control))


if __name__ == "__main__":
    main()
