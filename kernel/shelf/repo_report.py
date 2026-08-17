"""CARD: repo_report -- synthesize the whole Reverse-Engineering Lab into one repo report.

The unifier of the Reverse-Engineering Lab shelf: run every single-snapshot rung over one
package and fold the results into a single, honest RepoReport a human reads in one pass -
architecture, data model, API surface, code health, and the invocation surface, each with
the rung's own confidence, plus one OVERALL confidence that is the WEAKEST link (never
rounded up).

Composes seven rungs (the eighth, api_diff, needs two versions and is not part of a
single-snapshot synthesis):
  repo_analyzer   -> architecture (import graph, cycles, hubs)
  model_extractor -> data model (entities, relationships, state machines)
  call_graph      -> intra-module health (dead-code candidates)
  cross_module    -> API surface (keystones, unused-public candidates)
  control_flow    -> complexity (deep / many-exit functions)
  cli_surface     -> invocation + configuration surface

It presents nothing as proven fact: the overall confidence is the MINIMUM across rungs,
so one blind rung honestly caps the whole report. The candidate lists it surfaces
(dead-code, unused-public) keep the same human-filter caveats their own parts state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kernel.shelf import (
    call_graph,
    cli_surface,
    control_flow,
    cross_module,
    model_extractor,
    repo_analyzer,
)


@dataclass(frozen=True)
class RepoReport:
    """The unified reverse-engineering report of one package."""

    package: str
    module_count: int = 0
    # architecture
    hubs: tuple[str, ...] = ()
    import_cycles: int = 0
    externals: tuple[str, ...] = ()
    # data model
    entities: int = 0
    relationships: int = 0
    state_machines: int = 0
    # api surface
    public_symbols: int = 0
    keystones: tuple[str, ...] = ()  # cross-module hubs
    unused_public_candidates: int = 0
    # health
    dead_code_candidates: int = 0
    complex_functions: int = 0
    # invocation
    subcommands: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()
    # honesty
    rung_confidence: dict[str, float] = field(default_factory=dict)
    overall_confidence: float = 1.0


def synthesize(modules: dict[str, str], *, package: str = "") -> RepoReport:
    """Run every single-snapshot Lab rung over a package and fold into one RepoReport."""
    if not isinstance(modules, dict):
        raise TypeError("modules must be a dict of {module_name: source}")  # noqa: TRY003

    conf: dict[str, float] = {}

    arch = repo_analyzer.analyze_repo(modules, package=package)
    conf["architecture"] = arch.confidence

    cross = cross_module.analyze_repo(modules, package=package)
    conf["api_surface"] = cross.confidence

    entities = relationships = state_machines = 0
    dead = complex_n = 0
    subcommands: list[str] = []
    env_vars: set[str] = set()
    model_conf = flow_conf = cli_conf = call_conf = 1.0

    for name, source in modules.items():
        try:
            mr = model_extractor.analyze(source, module=name)
            entities += len(mr.entities)
            relationships += len(mr.relationships)
            state_machines += len(mr.state_machines)
            model_conf = min(model_conf, mr.confidence)

            cg = call_graph.analyze(source, module=name)
            dead += len(cg.dead_code)
            call_conf = min(call_conf, cg.confidence)

            cf = control_flow.analyze(source, module=name)
            complex_n += len(cf.complex_functions)
            flow_conf = min(flow_conf, cf.confidence)

            cs = cli_surface.analyze(source, module=name)
            subcommands.extend(cs.subcommands)
            env_vars.update(e.name for e in cs.env_vars)
            cli_conf = min(cli_conf, cs.confidence)
        except (SyntaxError, ValueError):
            # a single unparseable module lowers per-rung confidence but never aborts
            model_conf = min(model_conf, 0.5)

    conf["data_model"] = round(model_conf, 2)
    conf["health"] = round(min(call_conf, flow_conf), 2)
    conf["invocation"] = round(cli_conf, 2)

    overall = round(min(conf.values()), 2) if conf else 1.0
    return RepoReport(
        package=package,
        module_count=len(modules),
        hubs=arch.hubs,
        import_cycles=len(arch.cycles),
        externals=arch.externals,
        entities=entities,
        relationships=relationships,
        state_machines=state_machines,
        public_symbols=len(cross.symbols),
        keystones=cross.hubs[:8],
        unused_public_candidates=len(cross.unused_public),
        dead_code_candidates=dead,
        complex_functions=complex_n,
        subcommands=tuple(sorted(set(subcommands))),
        env_vars=tuple(sorted(env_vars)),
        rung_confidence=conf,
        overall_confidence=overall,
    )


def render(report: RepoReport) -> str:
    """A one-pass human-readable rendering of the unified report."""
    conf_line = (
        f"  modules: {report.module_count}   overall confidence: {report.overall_confidence} "
        "(the weakest rung, never rounded up)"
    )
    model_line = (
        f"    entities: {report.entities}   relationships: {report.relationships}   "
        f"state machines: {report.state_machines}"
    )
    lines = [
        f"=== REVERSE-ENGINEERING REPORT: {report.package or '<package>'} ===",
        conf_line,
        "",
        "  ARCHITECTURE",
        f"    hubs: {', '.join(report.hubs) or '(none)'}",
        f"    import cycles: {report.import_cycles}",
        f"    external deps: {len(report.externals)}",
        "  DATA MODEL",
        model_line,
        "  API SURFACE",
        f"    public symbols: {report.public_symbols}",
        f"    keystones: {', '.join(report.keystones) or '(none)'}",
        f"    unused-public candidates: {report.unused_public_candidates} (human-filtered)",
        "  CODE HEALTH",
        f"    dead-code candidates: {report.dead_code_candidates} (human-filtered)",
        f"    complex functions (deep/many-exit): {report.complex_functions}",
        "  INVOCATION",
        f"    subcommands: {', '.join(report.subcommands) or '(none)'}",
        f"    env vars: {', '.join(report.env_vars) or '(none)'}",
        "",
        "  PER-RUNG CONFIDENCE",
    ]
    for rung, c in report.rung_confidence.items():
        lines.append(f"    {rung}: {c}")
    return "\n".join(lines)
