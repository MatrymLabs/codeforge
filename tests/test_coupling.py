"""Test twin for parts/coupling.py -- the read-only engine coupling report (detachment D1).

Acceptance: analyze() classifies modules from injected traces (runtime-core, surface-optional,
unreached); render shows the counts + the honest "not a confirmed cut" caveat. Refusal: a trace
subprocess failure fails loud. A fake tracer keeps the suite fast and offline; the real subprocess
trace is exercised by `make coupling` / the verb.
"""

from __future__ import annotations

import parts.coupling as coupling_mod
from parts.coupling import CouplingError, analyze, render_report


def _fake_tracer(loaded_by: dict[tuple[str, ...], set[str]]):
    """A tracer returning a canned module set for a given command tuple."""
    return lambda commands: loaded_by[tuple(commands)]


def test_analyze_classifies_core_optional_and_unreached(monkeypatch):
    # Only these modules exist on disk, so classification is deterministic.
    monkeypatch.setattr(coupling_mod, "_all_modules", lambda: ["forgemod", "savemod", "arcmod"])
    base = tuple(coupling_mod.SURFACES["solo"])
    save = tuple(coupling_mod.SURFACES["solo"] + coupling_mod.SURFACES["save"])
    tracer = _fake_tracer({base: {"forgemod"}, save: {"forgemod", "savemod"}})
    report = analyze(tracer=tracer)
    assert report.runtime_core == ["forgemod"]
    assert report.surface_optional == {"save": ["savemod"]}
    assert report.unreached == ["arcmod"]  # loaded by no traced surface
    assert report.total == 3


def test_render_shows_counts_and_the_honest_caveat(monkeypatch):
    monkeypatch.setattr(coupling_mod, "_all_modules", lambda: ["a", "b"])
    base = tuple(coupling_mod.SURFACES["solo"])
    save = tuple(coupling_mod.SURFACES["solo"] + coupling_mod.SURFACES["save"])
    report = analyze(tracer=_fake_tracer({base: {"a"}, save: {"a"}}))
    out = render_report(report)
    assert "ENGINE COUPLING REPORT" in out
    assert "detachment CANDIDATES only" in out
    assert "NOT a confirmed-safe cut" in out  # the honesty caveat is always shown
    assert "b" in out  # the unreached candidate is named


def test_a_failed_trace_fails_loud(monkeypatch):
    def boom(commands):
        raise CouplingError("trace failed: exploded")

    with __import__("pytest").raises(CouplingError, match="exploded"):
        analyze(tracer=boom)


def test_coupling_verb_reachable_through_the_engine_tick(monkeypatch):
    # Patch the real tracer so the tick test does not spawn subprocesses.
    monkeypatch.setattr(coupling_mod, "_all_modules", lambda: ["core", "dev"])
    monkeypatch.setattr(coupling_mod, "_real_tracer", lambda commands: {"core"})
    from forge import handle_command
    from parts.session import Session

    out = handle_command(Session(player_id="matrym", location="courtyard"), "coupling")
    assert "ENGINE COUPLING REPORT" in out
