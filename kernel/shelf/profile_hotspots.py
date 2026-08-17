"""CARD: profile_hotspots -- read a cProfile run and rank where the time actually went.

The third rung of the R&D Debugging Lab (the optimization half of the "Automating
Debugging, Fixing, Optimization" brief: "profile -> hotspot -> gated change"). Given the
raw stats from a `cProfile`/`pstats` run, rank the functions by self time (where the CPU
actually is) and cumulative time (which call trees dominate), so a human knows where to
look BEFORE changing anything.

This is the "hotspot" step only. The brief is emphatic that a change is NOT justified by a
hotspot alone: "no benchmark improvement + identical test results = don't merge." So the
report carries that gate as a caveat and invents no verdict - it points, it does not fix.

The stats are INJECTED (a seam): `analyze` takes the raw `pstats` mapping, so tests never
have to run a real profile. `profile_call` is a convenience that runs `cProfile` on a
callable for real use / dogfooding.

Clean-room, stdlib only (`cProfile`, `pstats`).
"""

from __future__ import annotations

import cProfile
import pstats
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

CAVEAT = (
    "A hotspot is where time went in THIS run on THIS workload, not a proven bottleneck "
    "for all inputs. cProfile adds deterministic overhead (use a sampling profiler for "
    "production). Gate any change by a benchmark: no measured improvement + identical "
    "tests = do not merge."
)

# a pstats stats mapping: {(filename, lineno, funcname): (cc, nc, tottime, cumtime, callers)}
StatsKey = tuple[str, int, str]
StatsValue = tuple[int, int, float, float, dict[Any, Any]]


class ProfileError(ValueError):
    """Raised on malformed stats or an unknown sort key."""


@dataclass(frozen=True)
class Hotspot:
    """One function and its share of the run's time."""

    function: str  # "file.py:42(name)"
    calls: int
    self_time: float  # tottime: time in the function itself, excluding subcalls
    cumulative_time: float  # cumtime: including subcalls
    self_percent: float  # self_time as a share of the run's total self time


@dataclass(frozen=True)
class ProfileReport:
    """The ranked hotspot report - a pointer to where to look, never a fix."""

    hotspots: tuple[Hotspot, ...] = ()  # ranked by the chosen sort key, descending
    total_self_time: float = 0.0
    sort: str = "self"
    caveat: str = CAVEAT
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def prime_hotspot(self) -> str:
        return self.hotspots[0].function if self.hotspots else ""


def _fmt_key(key: StatsKey) -> str:
    filename, lineno, funcname = key
    short = filename.rsplit("/", 1)[-1] if filename not in ("~", "") else filename
    return f"{short}:{lineno}({funcname})"


def analyze(
    stats: dict[StatsKey, StatsValue],
    *,
    top: int = 15,
    sort: str = "self",
) -> ProfileReport:
    """Rank functions from a raw pstats mapping. sort = 'self' (tottime) or 'cumulative'.

    The mapping is the `pstats.Stats.stats` dict; use `from_stats`/`profile_call` to build
    one from a real run.
    """
    if sort not in ("self", "cumulative"):
        raise ProfileError(f"unknown sort {sort!r}; choose 'self' or 'cumulative'")  # noqa: TRY003
    if not isinstance(stats, dict):
        raise ProfileError("stats must be a pstats mapping {(file, line, func): (...)}")  # noqa: TRY003

    total_self = 0.0
    rows: list[tuple[StatsKey, int, float, float]] = []
    for key, value in stats.items():
        try:
            _cc, nc, tottime, cumtime, _callers = value
        except (ValueError, TypeError) as exc:
            raise ProfileError(f"malformed stats row for {key!r}: {exc}") from exc  # noqa: TRY003
        total_self += tottime
        rows.append((key, nc, tottime, cumtime))

    notes: list[str] = []
    if total_self <= 0.0:
        notes.append(
            "total self time is zero: the run was too fast to attribute (profile more work)"
        )

    if sort == "self":
        rows.sort(key=lambda r: (-r[2], _fmt_key(r[0])))  # tottime
    else:
        rows.sort(key=lambda r: (-r[3], _fmt_key(r[0])))  # cumtime

    hotspots = tuple(
        Hotspot(
            function=_fmt_key(key),
            calls=nc,
            self_time=round(tottime, 6),
            cumulative_time=round(cumtime, 6),
            self_percent=round(100.0 * tottime / total_self, 2) if total_self > 0 else 0.0,
        )
        for key, nc, tottime, cumtime in rows[:top]
    )
    return ProfileReport(
        hotspots=hotspots,
        total_self_time=round(total_self, 6),
        sort=sort,
        notes=tuple(notes),
    )


def from_stats(stats: pstats.Stats, *, top: int = 15, sort: str = "self") -> ProfileReport:
    """Build a report from a `pstats.Stats` object (e.g. loaded from a .prof file)."""
    raw: dict[StatsKey, StatsValue] = getattr(stats, "stats", {})
    return analyze(raw, top=top, sort=sort)


def profile_call(
    fn: Callable[..., Any],
    *args: Any,
    top: int = 15,
    sort: str = "self",
    **kwargs: Any,
) -> ProfileReport:
    """Run `fn(*args, **kwargs)` under cProfile and return the hotspot report (real use)."""
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        fn(*args, **kwargs)
    finally:
        profiler.disable()
    return from_stats(pstats.Stats(profiler), top=top, sort=sort)


def render(report: ProfileReport, *, top: int = 10) -> str:
    """A human-readable rendering of the ranked hotspots."""
    header = (
        f"profile hotspots (by {report.sort} time): "
        f"total self time {report.total_self_time}s across the run"
    )
    lines = [header]
    for note in report.notes:
        lines.append(f"  note: {note}")
    if report.hotspots:
        lines.append("  hotspots (where to look, not what to fix):")
        for h in report.hotspots[:top]:
            lines.append(
                f"    {h.self_percent:5.1f}%  self {h.self_time:.4f}s  "
                f"cum {h.cumulative_time:.4f}s  x{h.calls}  {h.function}"
            )
    else:
        lines.append("  no functions recorded")
    lines.append("  CAVEAT: " + report.caveat)
    return "\n".join(lines)
