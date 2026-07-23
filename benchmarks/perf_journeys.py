"""Performance measurement harness for CodeForge's five critical journeys.

MEASUREMENT ONLY -- no optimization. Reuses the frameless method of parts/bench.py (stdlib
time.perf_counter + statistics; a warmup pass; median + distribution). Startup is measured
COLD (a fresh interpreter per rep); the other four WARM (steady state). Raw per-run stats are
written to reports/performance/raw/ and a summary is printed and returned.

Run: python -m benchmarks.perf_journeys
"""

from __future__ import annotations

import json
import statistics
import subprocess  # nosec B404 -- fixed argv, no shell, used only to time a cold `import forge`
import sys
import time
from collections.abc import Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_RAW = _ROOT / "reports" / "performance" / "raw"


def _stats(samples_us: list[float]) -> dict:
    s = sorted(samples_us)
    n = len(s)
    return {
        "reps": n,
        "median_us": round(statistics.median(s), 2),
        "min_us": round(s[0], 2),
        "max_us": round(s[-1], 2),
        "stdev_us": round(statistics.pstdev(s), 2) if n > 1 else 0.0,
        "p95_us": round(s[min(n - 1, int(0.95 * (n - 1)))], 2),
    }


def _measure(call: Callable[[], object], reps: int, warmup: int) -> dict:
    perf = time.perf_counter
    for _ in range(warmup):
        call()
    out: list[float] = []
    for _ in range(reps):
        t = perf()
        call()
        out.append((perf() - t) * 1e6)
    return _stats(out)


def measure_startup(reps: int = 15) -> dict:
    """Cold start: time `import forge` in a fresh interpreter (imports ~40 parts, loads seeds)."""
    perf = time.perf_counter
    out: list[float] = []
    for _ in range(reps):
        t = perf()
        subprocess.run(  # nosec B603 -- fixed argv, no shell, no user input
            [sys.executable, "-c", "import forge"],
            cwd=_ROOT,
            check=True,
            capture_output=True,
        )
        out.append((perf() - t) * 1e6)
    st = _stats(out)
    st["kind"] = "cold_subprocess"
    return st


def run() -> dict[str, dict]:
    """Measure all five journeys and return {journey: stats}. Imports the real handlers."""
    from forge import handle_command
    from parts.bench import benchmark as command_bench
    from parts.qualitygate import render_gate_all
    from parts.workshop import reuse_search
    from parts.world import npcs
    from parts.world.jobs import bind_calling
    from parts.world.session import Session

    results: dict[str, dict] = {}

    # 1. startup (cold) -----------------------------------------------------------
    results["startup"] = measure_startup()

    # 2. one command (reuse the established engine-tick benchmark) -----------------
    cmd = command_bench(iterations=20_000, warmup=500)
    results["command"] = {
        "reps": cmd.samples,
        "median_us": round(cmd.median_us, 2),
        "p95_us": round(cmd.p95_us, 2),
        "p99_us": round(cmd.p99_us, 2),
        "max_us": round(cmd.max_us, 2),
        "throughput_per_s": round(cmd.throughput_per_s, 0),
        "kind": "warm_rotation",
    }

    # 3. one combat sequence (single strike; reset dummy HP per rep so it is comparable) ---
    fighter = Session(player_id="_bench", location="courtyard")
    bind_calling(fighter, "vanguard")
    from parts.world.npcs import trace_npc

    dummy_id = trace_npc("dummy", "courtyard")
    assert dummy_id is not None, "expected a training dummy in courtyard"
    full_hp = npcs.NPCS[dummy_id]["hp"]

    def combat_call() -> None:
        npcs.NPCS[dummy_id]["hp_now"] = full_hp  # a strike mutates hp_now; reset keeps it steady
        handle_command(fighter, "attack dummy")

    results["combat"] = {**_measure(combat_call, reps=5_000, warmup=500), "kind": "warm_strike"}

    # 4. registry / QA gate (grade every filed object; read-only) ------------------
    results["qa_gate_all"] = {**_measure(render_gate_all, reps=200, warmup=20), "kind": "warm"}

    # 5. library / registry search (Hardware Store catalog search; in-repo, deterministic) ---
    results["catalog_search"] = {
        **_measure(lambda: reuse_search("engine"), reps=2_000, warmup=200),
        "kind": "warm",
    }

    return results


def _table(results: dict[str, dict]) -> str:
    """The aligned journey/median/p95/max/reps table, shared by the console and the report."""
    lines = [f"{'journey':<18}{'median_us':>12}{'p95_us':>10}{'max_us':>10}{'reps':>8}  kind"]
    for name, st in results.items():
        lines.append(
            f"{name:<18}{st.get('median_us', 0):>12}{st.get('p95_us', 0):>10}"
            f"{st.get('max_us', 0):>10}{st.get('reps', 0):>8}  {st.get('kind', '')}"
        )
    return "\n".join(lines)


def render_journeys(results: dict[str, dict]) -> str:
    """The human-readable dated report of a five-journey run (mirrors `render_bench`)."""
    return "\n".join(
        [
            "FIVE-JOURNEY PERFORMANCE BENCHMARK - startup, command, combat, qa gate, catalog",
            "",
            _table(results),
            "",
            "  Startup is COLD (a fresh interpreter per rep); the rest WARM (steady state).",
            "  Renders never mutate state (architecture law 1), so the warm rotations repeat.",
            "  Measured on this host; numbers scale with CPU. Reproducible:",
            "  `python -m benchmarks.perf_journeys`.",
        ]
    )


def write_journeys_report(
    results: dict[str, dict], root: Path | None = None, stamp: str | None = None
) -> Path:
    """File the run as dated performance evidence under reports/performance/ (like the tick)."""
    from parts.shelf.reporting import write_report

    return write_report(
        "performance", render_journeys(results), root=root, stamp=stamp, slug="five-journeys"
    )


def main() -> None:
    results = run()
    _RAW.mkdir(parents=True, exist_ok=True)
    (_RAW / "five-journeys-raw.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(render_journeys(results))
    path = write_journeys_report(results)
    print(f"\n  evidence -> {path}")


if __name__ == "__main__":
    main()
