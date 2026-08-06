"""A narrow, non-executable declarative command DSL experiment.

The experiment intentionally compiles to a command contract. It never evaluates source code, loads
imports, or owns runtime state; the existing Seed command spine remains the execution authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_ID = re.compile(r"^[a-z][a-z0-9_.-]+$")
_FIELDS = {"command", "verb", "argument", "requires", "summary", "fallback", "effects"}


class CommandDslError(ValueError):
    """A command DSL document is malformed or attempts unsupported behavior."""


@dataclass(frozen=True)
class CommandDslComparison:
    """Evidence from comparing one bounded DSL command with one existing Lua behavior.

    This report measures the experiment; it does not select a runtime or make Lua part of the
    command authority.  A missing Lua extra is recorded honestly as unavailable.
    """

    command_id: str
    dsl_contract: dict[str, object]
    lua_available: bool
    lua_status: str
    lua_output: tuple[str, ...]
    lua_source_digest: str
    dimensions: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment": "command-dsl-vs-lua/1",
            "command_id": self.command_id,
            "dsl_contract": dict(self.dsl_contract),
            "lua": {
                "available": self.lua_available,
                "status": self.lua_status,
                "output": list(self.lua_output),
                "source_digest": self.lua_source_digest,
            },
            "dimensions": dict(self.dimensions),
            "decision": "experiment-only",
        }


@dataclass(frozen=True)
class DeclarativeCommand:
    command_id: str
    verb: str
    argument: str
    required_capability: str
    summary: str
    fallback: str
    effects: str = "none"
    schema_version: str = "1"

    def __post_init__(self) -> None:
        for value, field in (
            (self.command_id, "command_id"),
            (self.verb, "verb"),
            (self.required_capability, "required_capability"),
            (self.summary, "summary"),
            (self.fallback, "fallback"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise CommandDslError(f"{field} must not be empty")
        if not _ID.fullmatch(self.command_id) or not _ID.fullmatch(self.required_capability):
            raise CommandDslError("command_id and required capability must be safe identifiers")
        if self.effects not in {"none", "read", "write"}:
            raise CommandDslError("effects must be none, read, or write")

    def contract(self) -> dict[str, object]:
        return {
            "command_id": self.command_id,
            "canonical_name": self.verb,
            "argument_schema": {self.argument: {"type": "text"}} if self.argument else {},
            "required_capabilities": [self.required_capability],
            "side_effects": [] if self.effects == "none" else [self.effects],
            "plain_language_summary": self.summary,
            "text_fallback": self.fallback,
            "schema_version": self.schema_version,
        }


def parse_command_dsl(source: str) -> DeclarativeCommand:
    """Parse the small line-oriented experiment; unknown fields fail loudly."""
    values: dict[str, str] = {}
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        field, separator, value = line.partition(":")
        field, value = field.strip(), value.strip()
        if not separator or field not in _FIELDS or not value:
            raise CommandDslError(f"line {line_number}: expected '<field>: <value>'")
        if field in values:
            raise CommandDslError(f"line {line_number}: duplicate field {field!r}")
        values[field] = value
    required = {"command", "verb", "requires", "summary", "fallback"}
    missing = sorted(required - values.keys())
    if missing:
        raise CommandDslError(f"missing fields: {', '.join(missing)}")
    return DeclarativeCommand(
        command_id=values["command"],
        verb=values["verb"],
        argument=values.get("argument", ""),
        required_capability=values["requires"],
        summary=values["summary"],
        fallback=values["fallback"],
        effects=values.get("effects", "none"),
    )


def compare_command_implementations(
    dsl_source: str,
    lua_source: str,
    *,
    instruction_budget: int = 20_000,
) -> CommandDslComparison:
    """Compare one DSL contract with an equivalent bounded Lua snippet.

    The Lua path uses the existing deny-by-default sandbox and never receives Seed capabilities.
    The report is useful even when the optional Lua dependency is absent, because that absence is
    itself part of the adoption evidence.
    """
    command = parse_command_dsl(dsl_source)
    if not isinstance(lua_source, str) or not lua_source.strip():
        raise CommandDslError("lua_source must not be empty")
    digest = hashlib.sha256(lua_source.encode("utf-8")).hexdigest()
    from kernel.scripting import LuaSandbox, ScriptError, scripting_available

    available = scripting_available()
    status = "unavailable"
    output: tuple[str, ...] = ()
    if available:
        try:
            result = LuaSandbox(instruction_budget=instruction_budget).run(lua_source)
        except ScriptError as exc:
            status = f"error:{type(exc).__name__}"
        else:
            status = "passed"
            output = tuple(result.output)
    dimensions = {
        "diagnostics": "DSL has field/line diagnostics; Lua reports runtime or syntax errors",
        "capability_enforcement": "DSL declares a required capability; Lua receives no host grants",
        "accessibility": "DSL requires a plain-language fallback; Lua output needs an adapter",
        "migration": "DSL has a schema version; Lua migration remains source-owned",
        "debugging": "DSL has a typed contract; Lua debugging is sandbox/runtime dependent",
        "maintenance": "DSL contract is inspectable; Lua behavior remains opaque source",
    }
    return CommandDslComparison(
        command_id=command.command_id,
        dsl_contract=command.contract(),
        lua_available=available,
        lua_status=status,
        lua_output=output,
        lua_source_digest=f"sha256:{digest}",
        dimensions=dimensions,
    )
