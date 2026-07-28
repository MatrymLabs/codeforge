# ADR-0014: Embedded scripting (sandboxed Lua)

Status: Accepted (2026-07-28)

## Context

The polyglot organs so far reach for a language to *accelerate* a hot path (Rust, C++, C), to move a
boundary (Go), to define a contract (Protocol Buffers), or to query data (SQL). One capability none of
them provides is **letting a human who is not the engine author write behaviour and run it safely** --
scripted NPCs, room hooks, creator experiments. That is exactly what **Lua** exists for: it is the
classic embedded scripting language (games, Redis, nginx, Neovim). So the final organ embeds real Lua.

This is a different shape from the accelerator ADRs. There is no Python "fallback that does the same
thing" and no speedup to measure -- the capability is *new*. What matters instead is that untrusted
script code **cannot escape**. So the evidence for this organ is a **safety suite**, not a benchmark.

## Decision

Adopt Lua as an **optional, sandboxed** scripting engine, embedded via `lupa` (which bundles the Lua
runtime). The organ keeps the discipline's spirit, re-read for a capability rather than an accelerator:

1. **Optional, game-untouched when absent.** Lua ships as the `[lua]` extra, not a core dependency.
   When it is not installed, `parts.scripting.scripting_available()` is False, the `@script` console
   says so cleanly, and the full `make check` is green with no Lua runtime. Nothing hard-depends on it.
2. **A narrow, safe interface.** `parts.scripting.LuaSandbox.run(code) -> ScriptResult`. Scripts get a
   value back and may `emit()` output; that is the whole surface.
3. **Deny-by-default sandbox (the safety property, in place of parity).** A script runs with a fresh
   whitelist `_ENV` -- `math`, `string`, `table`, and a curated few -- so `os`, `io`, `require`,
   `load`, `dofile`, `package`, and `debug` are simply *not reachable*. A Lua debug hook counts
   instructions and aborts past a budget, so a runaway loop cannot hang the engine; the counter lives
   in the runtime globals, outside the script's `_ENV`, so a script cannot disarm it. Each run gets a
   fresh environment, so scripts cannot bleed into one another.
4. **The safety suite is the evidence.** `tests/test_scripting.py` proves each dangerous capability is
   denied, that a runaway loop is bounded, that a syntax error is reported (never raised raw), and that
   runs are isolated -- the parity-equivalent for a capability organ. There is deliberately no
   benchmark: speed is not the point, containment is.
5. **Governance.** `lupa` and Lua are recorded in `intake_ledger.toml` and pass `make intake`; the Lua
   runtime is confined to the optional `[lua]` path, never the game's core dependency set.
6. **Isolation.** A dedicated, **non-required** CI job (`lua`) installs the extra and runs the full
   safety suite; the base gate runs on the "scripting unavailable" fallback, so a Lua-runtime hiccup
   never blocks a merge.

## Honest limits

The sandbox denies **capabilities** (no filesystem, network, process, or host reach) and bounds
**execution** (no infinite loop). It does **not** bound **memory**: a deliberate single huge allocation
(e.g. `string.rep(x, 1e9)`) is out of scope, because Lua string methods reach the runtime's string
library through the string metatable regardless of `_ENV`. This is stated plainly, never papered over;
memory bounding (a custom Lua allocator) is future work, and the `@script` console is owner-only in the
meantime.

## First application

`@script <lua>` (`CMD-10.025`) -- an owner-only in-game console that runs a snippet in a `LuaSandbox`
and returns its output and value, or a clean `[script error]` on any violation. The sandbox is the
boundary, so even the owner's console cannot reach the host.

## Consequences

- **Positive:** the game gains safe user extensibility in the language built for it; the polyglot
  breadth now spans acceleration, services, contracts, data, and *scripting*; and the sandbox's
  guarantees are demonstrated by an adversarial test suite, not asserted.
- **Costs / risks:** a Lua runtime to keep current; a sandbox whose whitelist must stay tight (the
  safety suite guards it); the documented memory limitation. All bounded by the optional extra: absent
  or broken, scripting is simply off and the game is unaffected.
- **Exit:** delete `parts/scripting.py`, the `@script` command, and the `[lua]` extra; nothing else
  depends on them.
