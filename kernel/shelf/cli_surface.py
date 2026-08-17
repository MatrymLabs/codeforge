"""CARD: cli_surface -- reverse-engineer a program's invocation and configuration surface.

Batch 8 of the R&D Tech Lab Reverse-Engineering Lab: read a module and infer HOW A HUMAN
RUNS AND CONFIGURES IT - the argparse command-line surface (subcommands, options, whether
each is required, its default) and the environment variables it reads
(`os.environ[...]` / `os.getenv(...)`). This is the operational contract a README should
state and a reviewer wants without running the program.

Two extractions:
  * cli - argparse arguments/options and `add_subparsers` subcommands, each with its flag
    string, `required`, and `default` where statically visible.
  * env - environment variables read, with the default passed to `getenv` when present.

It never claims the surface is complete. Options built dynamically (a flag name from a
variable, `parser.add_argument(*computed)`), or a different framework (click/typer) beyond
argparse + os.environ, are recorded as unknowns and lower confidence. It reports what is
statically declared, and says where it is blind.

Clean-room, stdlib only (Python's own `ast`). Scope: one Python module.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


class CliSurfaceError(ValueError):
    """Raised when the source cannot be parsed."""


@dataclass(frozen=True)
class Option:
    """One argparse argument/option."""

    flags: tuple[str, ...]  # ("-v", "--verbose") or ("path",) for a positional
    positional: bool
    required: bool
    default: str  # the default as written, or "" if none/dynamic


@dataclass(frozen=True)
class EnvVar:
    """One environment variable the program reads."""

    name: str
    default: str  # the default passed to getenv, or "" if none / os.environ[...]
    has_default: bool


@dataclass(frozen=True)
class CliSurfaceReport:
    """The validated invocation/configuration surface of one module."""

    module: str
    subcommands: tuple[str, ...] = ()
    options: tuple[Option, ...] = ()
    env_vars: tuple[EnvVar, ...] = ()
    unknowns: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 1.0


def _literal(node: ast.expr | None) -> tuple[str, bool]:
    """(text, is_static) for an argument value."""
    if node is None:
        return "", False
    if isinstance(node, ast.Constant):
        return str(node.value), True
    return "", False


def _add_argument(call: ast.Call, out: list[Option], unknowns: list[str]) -> None:
    flags: list[str] = []
    dynamic = False
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            flags.append(arg.value)
        else:
            dynamic = True
    if dynamic or not flags:
        unknowns.append("add_argument with a non-literal flag name")
        if not flags:
            return
    positional = not flags[0].startswith("-")
    required = positional
    default = ""
    for kw in call.keywords:
        if kw.arg == "required" and isinstance(kw.value, ast.Constant):
            required = bool(kw.value.value)
        elif kw.arg == "default":
            text, static = _literal(kw.value)
            default = text
            if not static:
                default = "<dynamic>"
    out.append(Option(tuple(flags), positional, required, default))


def _env_read(call: ast.Call, out: list[EnvVar]) -> None:
    """`os.getenv("X"[, default])` or `os.environ.get("X"[, default])`."""
    if not call.args:
        return
    first = call.args[0]
    if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
        return
    name = first.value
    if len(call.args) >= 2:  # noqa: PLR2004
        text, _ = _literal(call.args[1])
        out.append(EnvVar(name, text, True))
    else:
        out.append(EnvVar(name, "", False))


def analyze(source: str, *, module: str = "") -> CliSurfaceReport:  # noqa: PLR0912
    """Reverse-engineer the CLI + env surface of one module. Never raises on dynamic
    construction; it records the gap and lowers confidence."""
    try:
        tree = ast.parse(source, filename=module or "<source>")
    except SyntaxError as exc:
        raise CliSurfaceError(f"cannot parse {module or 'source'}: {exc}") from exc  # noqa: TRY003

    subcommands: list[str] = []
    options: list[Option] = []
    env_vars: list[EnvVar] = []
    unknowns: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method == "add_argument":
                _add_argument(node, options, unknowns)
            elif method == "add_parser" and node.args:
                if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    subcommands.append(node.args[0].value)
                else:
                    unknowns.append("add_parser with a non-literal subcommand name")
            elif method == "getenv" or (
                method == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "environ"
            ):
                _env_read(node, env_vars)
        # os.environ["X"] subscript read
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
        ):
            sub = node.slice
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                env_vars.append(EnvVar(sub.value, "", False))
        # detect click/typer usage we do NOT parse -> honest unknown
        if (
            isinstance(node, ast.Attribute)
            and node.attr in ("command", "option", "argument")
            and isinstance(node.value, ast.Name)
            and node.value.id in ("click", "typer", "app")
        ):
            unknowns.append(f"{node.value.id}.{node.attr} decorator not parsed (argparse-only)")

    # dedupe env vars by (name, default)
    seen: set[tuple[str, str, bool]] = set()
    uniq_env: list[EnvVar] = []
    for e in env_vars:
        ekey = (e.name, e.default, e.has_default)
        if ekey not in seen:
            seen.add(ekey)
            uniq_env.append(e)

    unknowns = sorted(set(unknowns))
    confidence = round(max(0.3, 1.0 - 0.1 * len(unknowns)), 2)
    return CliSurfaceReport(
        module=module,
        subcommands=tuple(subcommands),
        options=tuple(options),
        env_vars=tuple(uniq_env),
        unknowns=tuple(unknowns),
        confidence=confidence,
    )


def render(report: CliSurfaceReport) -> str:
    """A human-readable rendering of the invocation/configuration surface."""
    lines = [f"cli surface: {report.module or '<source>'}  (confidence {report.confidence})"]
    if report.subcommands:
        lines.append("  subcommands: " + ", ".join(report.subcommands))
    if report.options:
        lines.append("  options:")
        for o in report.options:
            req = "required" if o.required else "optional"
            dflt = f", default={o.default}" if o.default else ""
            lines.append(f"    - {' '.join(o.flags)} ({req}{dflt})")
    if report.env_vars:
        lines.append("  environment:")
        for e in report.env_vars:
            dflt = f" (default {e.default})" if e.has_default and e.default else ""
            lines.append(f"    - {e.name}{dflt}")
    if report.unknowns:
        lines.append("  UNKNOWNS (confidence reducers): " + "; ".join(report.unknowns))
    if not (report.subcommands or report.options or report.env_vars):
        lines.append("  no CLI or environment surface detected")
    return "\n".join(lines)
