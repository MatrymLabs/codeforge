"""CARD: scripting -- a sandboxed Lua interpreter for safe user/creator scripts.

Lua is the classic embedded scripting language (games, Redis, nginx), the right tool for the
one job the other organs do not: let a human who is NOT the engine author write behaviour
and run it safely. This organ embeds real Lua (via lupa) behind a deny-by-default sandbox.

Unlike the accelerator organs, there is no Python "fallback that does the same thing" and no speedup
to measure: the capability is new, so its evidence is a SAFETY suite (test_scripting.py), not a
benchmark. It is OPTIONAL (ADR-0014): when lupa is absent, `scripting_available()` is False and
the game runs untouched -- nothing hard-depends on a Lua runtime.

The sandbox (see docs/adr/0014-embedded-scripting.md):
- **deny-by-default environment.** A script runs with a fresh whitelist `_ENV` -- math/string/table
  and a curated few -- so os, io, require, load, dofile, package, debug are simply not reachable.
- **bounded execution.** A Lua debug hook counts instructions and aborts past a budget, so a runaway
  loop (`while true do end`) cannot hang the engine. The counter lives in the runtime globals,
  beyond the script's reach.
- **honest limits.** It denies capabilities and bounds loops; it does NOT bound memory (one huge
  allocation is out of scope). Stated plainly, never overclaimed.

Inputs:  a Lua source string.
Outputs: a ScriptResult (the script's return value + anything it emit()ed). A bad or unsafe script
         raises ScriptError, never escapes the sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - presence depends on whether the [lua] extra is installed
    from lupa import LuaError, LuaRuntime

    _HAS_LUA = True
except ImportError:  # pragma: no cover - the fallback path (no Lua runtime)
    _HAS_LUA = False


# The only names a script can see. Deny-by-default: everything not here (os, io, require, load,
# dofile, loadfile, package, debug, print, pcall, setmetatable, ...) is simply absent.
_SAFE_NAMES = (
    "math",
    "string",
    "table",
    "tostring",
    "tonumber",
    "type",
    "pairs",
    "ipairs",
    "next",
    "select",
    "error",
    "assert",
)


class ScriptError(Exception):
    """A script that failed: a sandbox violation, a syntax error, or the instruction budget."""


@dataclass(frozen=True)
class ScriptResult:
    """The outcome of a run: the script's return value and the lines it emit()ed, in order."""

    value: Any
    output: list[str]


def scripting_available() -> bool:
    """True when the Lua runtime (the [lua] extra) is installed, so scripting can run."""
    return _HAS_LUA


class LuaSandbox:
    """A reusable sandboxed Lua interpreter. Construct once, run many scripts; each run gets a fresh
    whitelist environment and a fresh instruction budget, so scripts cannot see or bleed into each
    other. Raises ScriptError at construction when Lua is unavailable."""

    def __init__(self, *, instruction_budget: int = 200_000) -> None:
        if not _HAS_LUA:
            raise ScriptError(
                "Lua scripting is unavailable (install the [lua] extra: pip install '.[lua]')"
            )
        self._budget = instruction_budget
        self._lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
        # The instruction-count hook that bounds runaway loops. __count/__budget live in the runtime
        # globals; the script's restricted _ENV cannot see them, so it cannot disarm the hook.
        self._lua.execute(
            f"__budget = {int(instruction_budget)}\n"
            "__count = 0\n"
            "debug.sethook(function()\n"
            "  __count = __count + 1\n"
            "  if __count > __budget then error('instruction budget exceeded', 2) end\n"
            "end, '', 1000)\n"
        )
        # Loads a chunk with a caller-supplied _ENV and runs it. `load` stays in the runtime (not
        # the script's env), so only this trusted loader can compile code.
        self._loader = self._lua.eval(
            "function(code, env)\n"
            "  local chunk, err = load(code, 'user-script', 't', env)\n"
            "  if not chunk then error(err) end\n"
            "  return chunk()\n"
            "end"
        )

    def _fresh_env(self, emit: Any) -> Any:
        """A new whitelist env table: the safe globals plus an emit() the script can call."""
        globals_ = self._lua.globals()
        env = self._lua.table_from({name: globals_[name] for name in _SAFE_NAMES})
        env["emit"] = emit
        return env

    def run(self, code: str) -> ScriptResult:
        """Compile + run `code` in a fresh sandbox. Returns its value + emitted lines, or raises
        ScriptError on any syntax error, sandbox violation, or budget overrun."""
        if not isinstance(code, str):
            raise ScriptError("script code must be a str")
        output: list[str] = []

        def emit(text: Any) -> None:
            output.append(str(text))

        self._lua.execute("__count = 0")  # reset the budget for this run
        try:
            value = self._loader(code, self._fresh_env(emit))
        except LuaError as exc:
            raise ScriptError(str(exc)) from exc
        return ScriptResult(value=value, output=output)


def main(
    argv: list[str] | None = None,
) -> None:  # pragma: no cover - a runnable demo, not unit-tested
    """Evaluate a Lua snippet in the sandbox: `python -m kernel.scripting 'return 2+2'`."""
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if not scripting_available():
        print("Lua scripting is not installed. Enable it with: pip install '.[lua]'")
        return
    code = args[0] if args else "emit('hello from sandboxed Lua'); return 21 * 2"
    try:
        result = LuaSandbox().run(code)
    except ScriptError as exc:
        print(f"script error: {exc}")
        return
    for line in result.output:
        print(line)
    if result.value is not None:
        print(f"=> {result.value}")


if __name__ == "__main__":  # pragma: no cover
    main()
