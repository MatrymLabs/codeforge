"""CARD: aethryn_passes -- ordered compiler foundation passes for Aethryn packets."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.world import aethryn_validation
from kernel.world.aethryn_diagnostics import DiagnosticReport, diagnostic
from kernel.world.aethryn_ir import WorldIR, build_world_ir
from kernel.world.aethryn_models import GenerationPacket, ValidationIssue
from kernel.world.aethryn_references import resolve_references
from kernel.world.aethryn_schema import SchemaRegistry, default_schema_registry


class PassManagerError(ValueError):
    """A compiler pass graph is missing or contradictory."""


@dataclass(frozen=True, slots=True)
class PassContext:
    """Inputs shared by deterministic compiler foundation passes."""

    packet: GenerationPacket
    root: Path | None
    registry: SchemaRegistry
    external_ids: dict[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PassOutput:
    """One pass output and its diagnostics."""

    pass_name: str
    value: Any
    diagnostics: DiagnosticReport


PassRunner = Callable[[PassContext, Mapping[str, PassOutput]], PassOutput]


@dataclass(frozen=True, slots=True)
class CompilerPass:
    """A named pass with explicit dependencies and a deterministic runner."""

    name: str
    dependencies: tuple[str, ...]
    run: PassRunner


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """The ordered outputs and merged diagnostics from a pass execution."""

    outputs: tuple[PassOutput, ...]
    diagnostics: DiagnosticReport

    @property
    def verdict(self) -> str:
        return self.diagnostics.verdict

    @property
    def ir(self) -> WorldIR | None:
        for output in self.outputs:
            if output.pass_name == "normalization":
                return output.value
        return None


class PassManager:
    """Register and execute an acyclic, dependency-ordered pass graph."""

    def __init__(self, passes: tuple[CompilerPass, ...] = ()) -> None:
        self._passes: dict[str, CompilerPass] = {}
        for compiler_pass in passes:
            self.register(compiler_pass)

    def register(self, compiler_pass: CompilerPass) -> None:
        """Add one pass and reject duplicate names."""
        if compiler_pass.name in self._passes:
            raise PassManagerError(f"compiler pass already registered: {compiler_pass.name}")
        self._passes[compiler_pass.name] = compiler_pass

    def ordered(self, targets: tuple[str, ...] | None = None) -> tuple[CompilerPass, ...]:
        """Return a stable topological order for all or selected target passes."""
        requested = set(targets or self._passes)
        unknown = requested - self._passes.keys()
        if unknown:
            raise PassManagerError(f"unknown compiler pass target(s): {sorted(unknown)}")
        needed: set[str] = set()

        def visit(name: str, trail: tuple[str, ...] = ()) -> None:
            if name in trail:
                cycle = " -> ".join((*trail, name))
                raise PassManagerError(f"compiler pass dependency cycle: {cycle}")
            if name in needed:
                return
            compiler_pass = self._passes[name]
            for dependency in compiler_pass.dependencies:
                if dependency not in self._passes:
                    raise PassManagerError(
                        f"compiler pass {name!r} depends on missing pass {dependency!r}"
                    )
                visit(dependency, (*trail, name))
            needed.add(name)

        for name in sorted(requested):
            visit(name)
        return tuple(self._passes[name] for name in self._passes if name in needed)

    def execute(
        self, context: PassContext, *, targets: tuple[str, ...] | None = None
    ) -> PipelineResult:
        """Execute selected passes in dependency order and merge their diagnostics."""
        outputs: dict[str, PassOutput] = {}
        report = DiagnosticReport()
        for compiler_pass in self.ordered(targets):
            output = compiler_pass.run(context, outputs)
            outputs[compiler_pass.name] = output
            report = report.merge(output.diagnostics)
        return PipelineResult(tuple(outputs.values()), report)


def _validation_diagnostics(issues: tuple[ValidationIssue, ...]) -> DiagnosticReport:
    return DiagnosticReport(
        tuple(
            diagnostic(
                issue.code,
                issue.message,
                subsystem=issue.category,
                source_path=issue.path,
                violated_rule=issue.authority,
                authority_source=issue.authority,
                suggested_correction=issue.action,
                severity="warning" if issue.severity == "warning" else "error",
            )
            for issue in issues
        )
    )


def _source_loading(context: PassContext, _outputs: Mapping[str, PassOutput]) -> PassOutput:
    return PassOutput("source_loading", context.packet, DiagnosticReport())


def _normalization(context: PassContext, _outputs: Mapping[str, PassOutput]) -> PassOutput:
    ir, report = build_world_ir(
        context.packet,
        context.registry,
        external_ids=context.external_ids,
    )
    return PassOutput("normalization", ir, report)


def _canon_validation(context: PassContext, _outputs: Mapping[str, PassOutput]) -> PassOutput:
    report = aethryn_validation.validate_packet(context.packet, root=context.root)
    return PassOutput("canon_validation", report, _validation_diagnostics(report.issues))


def _reference_resolution(context: PassContext, outputs: Mapping[str, PassOutput]) -> PassOutput:
    ir = outputs["normalization"].value
    if not isinstance(ir, WorldIR):
        raise PassManagerError("reference_resolution requires the normalization WorldIR output")
    return PassOutput("reference_resolution", ir, resolve_references(ir, context.registry))


def foundation_pass_manager() -> PassManager:
    """Return the currently implemented source, normalization, canon, and reference passes."""
    return PassManager(
        (
            CompilerPass("source_loading", (), _source_loading),
            CompilerPass("normalization", ("source_loading",), _normalization),
            CompilerPass("canon_validation", ("source_loading",), _canon_validation),
            CompilerPass(
                "reference_resolution",
                ("normalization",),
                _reference_resolution,
            ),
        )
    )


def run_foundation_pipeline(
    packet: GenerationPacket,
    *,
    root: Path | None = None,
    registry: SchemaRegistry | None = None,
    external_ids: dict[str, frozenset[str]] | None = None,
    targets: tuple[str, ...] | None = None,
) -> PipelineResult:
    """Run the implemented deterministic compiler foundation for one packet."""
    active_registry = registry or default_schema_registry()
    context = PassContext(
        packet=packet,
        root=root,
        registry=active_registry,
        external_ids=external_ids or {},
    )
    return foundation_pass_manager().execute(context, targets=targets)
