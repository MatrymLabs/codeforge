"""Test twin for parts.scripting -- the sandboxed Lua interpreter. The SAFETY suite is the evidence.

Acceptance: a safe script computes a value and emit()s output. Refusal (the whole point): every
dangerous capability -- os, io, require, load, dofile, package, debug -- is unreachable; a runaway
loop is bounded by the instruction budget; a syntax error is reported; runs are isolated from each
other. All raise ScriptError; nothing escapes the sandbox.

The sandbox tests need the [lua] extra; they skip cleanly when it is absent (the base gate), where
only the "scripting unavailable" fallback is asserted. The dedicated `lua` CI job installs lupa and
runs the full suite.
"""

from __future__ import annotations

import pytest

from parts.scripting import LuaSandbox, ScriptError, ScriptResult, scripting_available

_needs_lua = pytest.mark.skipif(
    not scripting_available(), reason="Lua runtime not installed (the [lua] extra)"
)


def test_scripting_available_is_a_bool():
    assert isinstance(scripting_available(), bool)


@pytest.mark.skipif(
    scripting_available(), reason="asserts the fallback, only meaningful without Lua"
)
def test_the_sandbox_refuses_to_build_without_lua():
    with pytest.raises(ScriptError, match="unavailable"):
        LuaSandbox()


@pytest.fixture
def sandbox() -> LuaSandbox:
    # a small budget so a runaway loop aborts fast; legit test scripts stay well under it
    return LuaSandbox(instruction_budget=20_000)


@_needs_lua
def test_a_safe_script_computes_a_value_and_emits(sandbox):
    result = sandbox.run("emit('forged'); local t = 0; for i = 1, 5 do t = t + i end; return t")
    assert isinstance(result, ScriptResult)
    assert result.value == 15
    assert result.output == ["forged"]


@_needs_lua
@pytest.mark.parametrize(
    "code",
    [
        "return os.time()",
        "return io.open('/etc/passwd')",
        "return require('os')",
        "return load('return 1')",
        "return dofile('/etc/passwd')",
        "return loadfile('/etc/passwd')",
        "return debug.getinfo(1)",
        "return package.loaded",
        "return setmetatable({}, {})",
    ],
)
def test_every_dangerous_capability_is_denied(sandbox, code):
    # deny-by-default: each of these is simply not in the script's environment, so it fails loud
    with pytest.raises(ScriptError):
        sandbox.run(code)


@_needs_lua
def test_a_runaway_loop_is_bounded_by_the_budget(sandbox):
    with pytest.raises(ScriptError, match="budget"):
        sandbox.run("while true do end")


@_needs_lua
def test_a_syntax_error_is_reported_not_raised_raw(sandbox):
    with pytest.raises(ScriptError):
        sandbox.run("this is not )( valid lua")


@_needs_lua
def test_non_str_code_fails_loud(sandbox):
    with pytest.raises(ScriptError, match="must be a str"):
        sandbox.run(123)  # not a str


@_needs_lua
def test_runs_are_isolated_from_each_other(sandbox):
    sandbox.run("leaked = 42")  # assigns into this run's disposable env, not a shared global
    assert sandbox.run("return leaked").value is None  # the next run cannot see it


@_needs_lua
def test_the_budget_resets_every_run(sandbox):
    # a heavy-but-legal loop succeeds, and repeating it proves the counter does not carry over
    for _ in range(3):
        assert (
            sandbox.run("local t = 0; for i = 1, 1000 do t = t + i end; return t").value == 500500
        )
