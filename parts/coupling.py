"""CARD: coupling -- read-only engine coupling report: what a cast could shed (detachment D1).

The vision's #1 architectural risk is the vendored-whole engine: a cast carries all ~120 `parts/`
modules, including the self-auditing engineering stack, the admin/API/CLI surfaces, and the
manufacturing tooling a shipped game never runs. Detachment (vendored-whole -> vendored-selective)
is the fix; this is its first, READ-ONLY phase (D1): it makes the coupling visible so a later,
keel-signed selective vendoring (D2) has evidence to cut on.

It TRACES the real runtime module closure per surface (boot `forge`, drive a command corpus, read
which `parts/*` actually loaded) - not a static import graph, which would miss the engine's many
lazy in-function imports. It writes nothing and changes no vendoring. See
docs/reports/2026-07-14-detachment-design.md for the D1..D3 plan.

Honesty: a command-trace closure only sees the commands it drives; a module a command lazily
imports on an untried path can be miscounted. So D1 REPORTS candidates; D2 must gate any actual
cut on a broad validation harness. No claim of a safe cut is made here.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 -- fixed argv, no shell; used only to trace a boot + commands
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

BASE_SURFACE = "solo"
# Additive command corpora per surface: `solo` is the base runtime game; each higher surface is
# traced as base + its own commands, so `surface_optional` is what that surface ALONE pulls in.
SURFACES: dict[str, list[str]] = {
    "solo": [
        "look",
        "help",
        "score",
        "inventory",
        "go n",
        "go s",
        "go e",
        "go w",
        "attack dummy",
        "quest",
        "catalog",
        "workshop",
        "progress",
        "achievements",
    ],
    "save": ["save", "load"],
}
# Server entry points a command trace cannot reach, but a multiplayer cast needs. Reported, honest.
_SERVER_ENTRYPOINTS = ("gateway", "web_gateway")

Tracer = Callable[[list[str]], set[str]]


class CouplingError(RuntimeError):
    """A trace subprocess failed: fail loud rather than report a dishonest closure."""


@dataclass(frozen=True)
class CouplingReport:
    """A read-only classification of `parts/` modules by how a runtime game reaches them."""

    total: int
    runtime_core: list[str]  # loaded by the base (solo) surface
    surface_optional: dict[str, list[str]]  # surface -> modules only that surface adds
    unreached: list[str]  # reached by no traced surface: detachment CANDIDATES, not confirmed cuts
    server_entrypoints: list[str]  # not command-traceable; needed for multiplayer


_TRACE_PROBE = r"""
import sys, json
import forge
from parts.session import Session
s = Session(player_id="_trace", location="courtyard")
for cmd in json.loads(sys.argv[1]):
    try:
        forge.handle_command(s, cmd)
    except Exception:
        pass
print(json.dumps(sorted({m.split(".")[1] for m in sys.modules if m.startswith("parts.")})))
"""


def _real_tracer(commands: list[str]) -> set[str]:
    """Boot the engine in a fresh interpreter, drive `commands`, return the `parts/*` loaded."""
    result = subprocess.run(  # nosec B603 -- fixed argv, no shell; traces a boot + commands
        [sys.executable, "-c", _TRACE_PROBE, json.dumps(commands)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CouplingError(f"trace failed: {result.stderr.strip()[-200:]}")
    return set(json.loads(result.stdout.strip() or "[]"))


def _all_modules() -> list[str]:
    return sorted(p.stem for p in (_ROOT / "parts").glob("*.py") if p.stem != "__init__")


def analyze(tracer: Tracer | None = None) -> CouplingReport:
    """Trace each surface's closure and classify every `parts/` module. Reads only."""
    trace = tracer or _real_tracer
    all_mods = _all_modules()
    base_cmds = SURFACES[BASE_SURFACE]
    core = trace(base_cmds)
    surface_optional: dict[str, list[str]] = {}
    covered = set(core)
    for surface, cmds in SURFACES.items():
        if surface == BASE_SURFACE:
            continue
        added = trace(base_cmds + cmds) - covered
        if added:
            surface_optional[surface] = sorted(added)
            covered |= added
    unreached = sorted(m for m in all_mods if m not in covered and m not in _SERVER_ENTRYPOINTS)
    server = sorted(m for m in _SERVER_ENTRYPOINTS if m in all_mods)
    return CouplingReport(
        total=len(all_mods),
        runtime_core=sorted(core),
        surface_optional=surface_optional,
        unreached=unreached,
        server_entrypoints=server,
    )


def render_report(report: CouplingReport) -> str:
    """The human view of the coupling report - counts, per-class modules, detachable candidates."""
    candidates = (
        sum(len(v) for v in report.surface_optional.values())
        + len(report.unreached)
        + len(report.server_entrypoints)
    )
    lines = [
        "ENGINE COUPLING REPORT (read-only, detachment D1 - nothing is changed or cut)",
        "",
        f"  total parts/ modules:         {report.total}",
        f"  runtime-core (solo game):     {len(report.runtime_core)}",
    ]
    for surface, mods in report.surface_optional.items():
        lines.append(f"  +{surface} adds:                {len(mods)}  ({', '.join(mods)})")
    lines += [
        f"  unreached by the trace:       {len(report.unreached)}  <- detachment CANDIDATES only",
        f"  server entry points:          {len(report.server_entrypoints)} "
        f"({', '.join(report.server_entrypoints)}) - needed for multiplayer, not command-traceable",
        "",
        f"  up to {candidates} of {report.total} modules were unreached by the traced surfaces.",
        "  NOT a confirmed-safe cut: this is a command-trace closure, so a module reached only on",
        "  an untried path (e.g. db=save, login_guard=auth, terminal=tty) is a FALSE candidate.",
        "  D2 (selective vendoring) must confirm every cut with a broad per-command harness first.",
        "",
        "  unreached candidates (verify, do not cut blindly): " + ", ".join(report.unreached),
    ]
    return "\n".join(lines)


def coupling(arg: str = "") -> str:
    """The read-only `coupling` verb: the engine coupling report (detachment D1)."""
    try:
        return render_report(analyze())
    except CouplingError as exc:
        return f"coupling: {exc}"


def main(argv: list[str] | None = None) -> int:
    """`make coupling`: print the read-only engine coupling report."""
    print(coupling())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
