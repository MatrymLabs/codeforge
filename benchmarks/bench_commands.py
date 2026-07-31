"""Benchmark: end-to-end command dispatch latency through the engine tick.

The prompt's performance mechanism asks to record command dispatch latency (p50/p95) on a
representative workload with a reproduction command. This drives a set of common commands through
`forge.handle_command` on a reused session (a connected player issuing many commands) and reports
median and p95 per command. Frameless (perf_counter + statistics), no test framework.

Run at world scale with the aethryn seed:

    FORGE_SEED=aethryn python benchmarks/bench_commands.py [runs]

Context (day-209 optimization campaign): the hot display commands were ~42ms each until three
measured fixes (zone_of reverse index #667, cached world NavGraph #668, incremental NPC roam index
#669) brought them under ~1ms. This benchmark is the standing evidence + regression signal for that.
"""

from __future__ import annotations

import statistics
import sys
import time

import forge
from parts.world.session import Session
from parts.world.world import START_ROOM

# A representative mix: display commands (the hot path), movement, and social verbs.
_COMMANDS = (
    "look", "score", "inventory", "skills", "equipment", "stats", "quests",
    "map", "who", "help", "time", "north", "south", "say hello", "emote nods",
)  # fmt: skip


def _latencies_us(session: Session, command: str, runs: int) -> list[float]:
    """Wall-clock microseconds for `runs` dispatches of one command on a warmed session."""
    forge.handle_command(session, command)  # warm
    out: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        forge.handle_command(session, command)
        out.append((time.perf_counter() - start) * 1e6)
    out.sort()
    return out


def _pct(sorted_us: list[float], pct: float) -> float:
    """The pct-th percentile of an already-sorted list (pct in 0..100)."""
    return sorted_us[min(len(sorted_us) - 1, int(len(sorted_us) * pct / 100))]


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    session = Session(player_id="bench", location=START_ROOM)
    print(f"command dispatch latency  (reused session, {runs} runs each)")
    print(f"{'command':16s} {'p50_us':>10s} {'p95_us':>10s} {'p99_us':>10s}")
    worst = 0.0
    for command in _COMMANDS:
        us = _latencies_us(session, command, runs)
        p50, p95, p99 = statistics.median(us), _pct(us, 95), _pct(us, 99)
        worst = max(worst, p50)
        print(f"{command:16s} {p50:10.1f} {p95:10.1f} {p99:10.1f}")
    print(f"\nworst p50 across the mix: {worst:.1f} us")


if __name__ == "__main__":
    main()
