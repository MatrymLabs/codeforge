# CodeForge Architecture

## The shape

A **pure engine tick** surrounded by thin drivers:

```
clients (Mudlet / telnet / nc / terminal)
   -> gateway front desk (authenticate BEFORE the world)
   -> handle_command(session, text) -> str    # the tick: one command in, one response out
   -> parts/* (world, items, doors, npcs, jobs, combat, ranks, accounts, ...)
   -> events bus (echo sinks per player; room broadcasts; shutdown hook)
   -> seeds/*.yaml + splash.txt (the world as data, gated at load)
   -> codeforge.db + save snapshots (minimal canonical state)
```

The tick is a plain function, so every driver -- the solo terminal loop, the threaded
TCP gateway, and any future WebSocket gateway -- is just another caller. The gateway's
login dialogue is deliberately thin UX: it assembles the same `login`/`register`
commands any player could type; authentication logic lives in one place.

## The three laws

1. **State is canonical; text is a projection.** `render_scene`, `render_sheet`, and
   every broadcast read state and return strings. Nothing rendered ever mutates.
2. **The world is data.** Seed loaders are gates: label format rules, duplicate-key
   refusal, template merge chains, cross-component location validation. A pack that
   fails validation never reaches the engine.
3. **Derive, don't store.** A character casefile is job + level + xp + location + rank
   + account. Stats and resources recompute on restore; a parity test pins
   restore-math == play-math forever.

## Concurrency model

Threads own sockets; the world processes **one command at a time** under a single
tick lock -- the classic MUD model. Broadcasts happen inside the tick, so delivery
is serialized. An async event-loop gateway is a future card, not a correction.

## Security model

- Authorization before capability: `@`-verbs check rank before any code runs.
- Accounts hold the password (salted pbkdf2-sha256, 600k iterations, constant-time
  compare); characters are masks worn by their account.
- Login refusals are generic -- no account/character/password enumeration.
- Bootstrap authority is the host shell (`codeforge grant`): physical access is the
  one rank the engine cannot outrank.
- Known debts, tracked: plaintext telnet transport (TLS/echo-masking are future
  cards); this is a LAN service, not an internet-facing one.

## Decision records

See `docs/adr/` for the load-bearing decisions and their reasoning.
