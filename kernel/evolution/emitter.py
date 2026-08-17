"""CARD: evolution.emitter -- express a validated genome into a reviewable phenotype scaffold.

RD-2026-0002 #10, the Blueprint Evolution Lab's missing "Build now" rung. The lab has the typed
schema (genome.py), the KeelGate (validation.py), and propose-only mutation (mutation.py) - but no
EMITTER, so a genome never becomes a genotype->phenotype expression. This is that step: from a
VALIDATED BlueprintGenome it emits a reviewable scaffold (a code skeleton honoring the declared
interfaces + invariants, a test skeleton from the test_obligations, a config/doc stub from the
budgets/doc obligations), one file per declared expression_target.

PROPOSE-ONLY, keel intact (the same line the whole lab draws): every emitted body raises
NotImplementedError and every file's header says a HUMAN implements and approves - drafting
a scaffold is not autonomous promotion. The emitter runs `validate_genome` FIRST and refuses to
express an invalid genome (fail-closed, so a bad genotype never becomes even a draft). Emitted code
is guaranteed to PARSE (a scaffold that will not import is worse than none).

Clean-room, stdlib only (`ast`, `re`).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from kernel.evolution.genome import BlueprintGenome, GenomeError
from kernel.evolution.validation import validate_genome

# a clean function/method signature, e.g. "format_row(text: str, width: int) -> str"
_SIGNATURE = re.compile(r"^[a-z_]\w*\s*\(.*\)(\s*->\s*.+)?$")
_LEADING_NAME = re.compile(r"^([a-z_]\w*)")
_NONWORD = re.compile(r"[^a-z0-9]+")


class EmitterError(ValueError):
    """Raised when a genome cannot be expressed (e.g. it fails the KeelGate)."""


@dataclass(frozen=True)
class Phenotype:
    """The emitted scaffold: one (filename, content) pair per expressed target. Draft, not code."""

    genome_id: str
    files: tuple[tuple[str, str], ...]

    def file(self, name: str) -> str | None:
        for fname, content in self.files:
            if fname == name:
                return content
        return None


def _slug(text: str) -> str:
    s = _NONWORD.sub("_", text.lower()).strip("_")
    if not s or not s[0].isalpha():
        s = f"scaffold_{s}" if s else "scaffold"
    return s


def _header(genome: BlueprintGenome, kind: str) -> str:
    return (
        f'"""PROPOSE-ONLY {kind} scaffold, expressed from genome {genome.genome_id!r}.\n\n'
        f"Purpose: {genome.purpose}\n"
        f"A HUMAN implements the bodies and approves promotion - this is a draft, not code "
        f"(mutation_policy={genome.mutation_policy}, approval_policy={genome.approval_policy}).\n"
        f'"""'
    )


def _def_stub(interface: str, index: int) -> str:
    """Emit a parseable `def` stub for one declared interface, however rough the declaration."""
    text = interface.strip()
    if _SIGNATURE.match(text):
        return f"def {text}:\n    raise NotImplementedError({interface!r})\n"
    # not a clean signature -> a safely-named stub carrying the raw interface as its docstring
    name = _LEADING_NAME.match(text)
    fn = name.group(1) if name else f"interface_{index}"
    body = f"    {interface!r}  # noqa: B018 -- declared interface\n    raise NotImplementedError\n"
    return f"def {fn}() -> None:\n{body}"


def _emit_code(genome: BlueprintGenome) -> str:
    lines = [_header(genome, "code"), ""]
    for dep in genome.allowed_dependencies:
        lines.append(f"# allowed dependency: import {dep}")
    for inv in genome.invariants:
        lines.append(f"# invariant (must always hold): {inv}")
    for metric, budget in genome.resource_budgets:
        lines.append(f"# budget: {metric} <= {budget}")
    lines.append("")
    if genome.interfaces:
        for i, iface in enumerate(genome.interfaces):
            lines.append(_def_stub(iface, i))
    else:
        fn = _slug(genome.purpose or genome.genome_id)
        lines.append(f"def {fn}() -> None:\n    raise NotImplementedError\n")
    return "\n".join(lines)


def _emit_tests(genome: BlueprintGenome) -> str:
    lines = [
        _header(genome, "tests"),
        "",
        "import unittest",
        "",
        "",
        f"class Test_{_slug(genome.genome_id)}(unittest.TestCase):",
    ]
    obligations = genome.test_obligations or ("the phenotype meets its interface",)
    for i, ob in enumerate(obligations):
        lines.append(f"    def test_{i}_{_slug(ob)[:40]}(self) -> None:")
        lines.append(f"        {ob!r}  # noqa: B018 -- declared test obligation")
        lines.append('        self.fail("TODO: a human writes this test")')
        lines.append("")
    return "\n".join(lines)


def _emit_config(genome: BlueprintGenome) -> str:
    lines = [
        f"# PROPOSE-ONLY config scaffold from genome {genome.genome_id} (a human fills real values)"
    ]
    for metric, budget in genome.resource_budgets:
        lines.append(f"{metric} = {budget}  # budget ceiling")
    for pol in genome.security_policies:
        lines.append(f"# security policy: {pol}")
    return "\n".join(lines) + "\n"


def _emit_docs(genome: BlueprintGenome) -> str:
    lines = [
        f"# {genome.genome_id}",
        "",
        "> PROPOSE-ONLY doc scaffold - a human writes the real content.",
        "",
        f"{genome.purpose}",
        "",
    ]
    for ob in genome.documentation_obligations:
        lines.append(f"- [ ] {ob}")
    return "\n".join(lines) + "\n"


_EMITTERS = {
    "code": (_emit_code, lambda g: f"{g.genome_id}.py"),
    "tests": (_emit_tests, lambda g: f"test_{g.genome_id}.py"),
    "config": (_emit_config, lambda g: f"{g.genome_id}.config.py"),
    "docs": (_emit_docs, lambda g: f"{g.genome_id}.md"),
}


def express(genome: BlueprintGenome) -> Phenotype:
    """Express a VALIDATED genome into a propose-only phenotype scaffold (one file per target).

    Runs the KeelGate first: an invalid genome is refused (fail-closed), so a bad genotype never
    becomes even a draft. With no expression_targets declared, defaults to code + tests. Emitted
    Python (code/tests/config) is guaranteed to parse."""
    try:
        validate_genome(genome)
    except GenomeError as exc:
        raise EmitterError(f"cannot express an invalid genome {genome.genome_id!r}: {exc}") from exc  # noqa: TRY003

    targets = genome.expression_targets or ("code", "tests")
    files: list[tuple[str, str]] = []
    for target in targets:
        emit_fn, name_fn = _EMITTERS[target]  # targets are validated to EXPRESSION_TARGETS upstream
        content = emit_fn(genome)
        if target in ("code", "tests", "config"):
            # a scaffold that will not import is worse than none - prove it parses before emitting
            try:
                ast.parse(content)
            except SyntaxError as exc:  # pragma: no cover - guards against a future template typo
                raise EmitterError(  # noqa: TRY003
                    f"emitted {target} for {genome.genome_id!r} does not parse: {exc}"
                ) from exc
        files.append((name_fn(genome), content))
    return Phenotype(genome_id=genome.genome_id, files=tuple(files))


def render(phenotype: Phenotype) -> str:
    """A readable listing of the emitted scaffold (a human reviews, fills, and approves)."""
    lines = [f"phenotype scaffold for {phenotype.genome_id} (PROPOSE-ONLY - a human implements):"]
    for fname, content in phenotype.files:
        lines.append(f"  {fname}  ({len(content.splitlines())} lines)")
    return "\n".join(lines)
