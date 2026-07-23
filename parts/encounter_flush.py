"""CARD: encounter_flush -- the trusted boundary: encounter tallies -> Chronicle metrics.

The retained leg of the aggression loop's observability. `parts/encounter_log` is written by the
player tick and imports nothing from the Chronicle, so the tick never gets a write path into the
tamper-evident ledger. This module is the OTHER side: it bridges the two, invoked ONLY by a trusted
actor -- an OWNER, via the owner-gated `@flush-encounters` verb, run IN the server process where the
tallies live (they are in-memory, so a separate CLI process would only ever see an empty period).

It reads a period's tallies, records ONE aggregate `metric` per non-zero kind into the Chronicle
(feeding the existing `chronicle trend` machinery), then clears the tallies so the next period
counts from zero. An empty period records nothing (honest: no noise for no encounters).

This is where `encounter_log` and `chronicle` are allowed to meet, at the boundary Josh controls.
"""

from __future__ import annotations

from pathlib import Path

from parts import chronicle
from parts.world import encounter_log

_METRIC_PREFIX = "encounters."  # one trend series per encounter kind, e.g. encounters.open_strike


def flush(commit: str, *, root: Path | None = None) -> str:
    """Record each non-zero encounter tally as an aggregate Chronicle metric, then clear the
    tallies. Returns a human summary. A period with no encounters records nothing and says so.
    `root` is the Chronicle ledger root (injected in tests so they never touch the real ledger)."""
    counts = encounter_log.tally()
    recorded = {kind: n for kind, n in counts.items() if n}
    if not recorded:
        return "No encounters this period; nothing flushed to the Chronicle."
    for kind, n in recorded.items():
        chronicle.record_metric(f"{_METRIC_PREFIX}{kind}", n, commit=commit, root=root)
    encounter_log.clear_tally()
    summary = ", ".join(f"{kind}={n}" for kind, n in recorded.items())
    return f"Flushed {len(recorded)} encounter metric(s) to the Chronicle @ {commit}: {summary}"
