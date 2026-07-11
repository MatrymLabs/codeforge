# ADR-0003: Framework-free by design

**Status:** accepted (revisable - this is a scope choice, not a permanent rule)

## Context

CodeForge's predecessor (`codeforge_mk1`, now the public `codeforge-evennia`) was built on
**Evennia**, a capable and well-regarded Python MUD framework layered on Django and Twisted.
Evennia is a good tool. Using it - or another framework - is a perfectly valid way to build
a MUD.

It is simply **out of scope for what CodeForge is trying to prove.** This project's goal is
to demonstrate building small, tested, reusable parts and a clear engine *from the ground
up* - the tick, the world model, the persistence, the networking, all in plain, inspectable
code. A framework provides much of that for you; leaning on one would hide the exact
engineering this portfolio exists to show. So CodeForge takes the framework-free path **by
design**, for its current scope - not as a verdict on any framework.

## Decision

CodeForge is **framework-free** for now: pure Python + `sqlalchemy` + `fastapi` + `uvicorn`
+ `websockets` + `pyyaml`, with its own engine, world model, and gateway. The supporting
design choices:

1. **The world is data.** Content lives in `seeds/*.yaml`, validated by loader gates. State
   is canonical; text is a projection (ADR-0001).
2. **One pure-function tick.** `handle_command(session, signal) -> str` is the only door; the
   command spine namespaces verbs (`CORE` / `ADMIN @` / `SEED`) in plain, testable code.
3. **Derive, don't store (ADR-0002).** Records persist minimal facts; stats and resources are
   immutable, validated dataclasses that import nothing from the engine.
4. **Small tested reusable parts.** Every module in `parts/` has one job, a `CARD:` line, and
   a test twin. Extension is composition.

**This decision stays open.** If the project's goals change - a larger world, a need for the
batteries a framework includes - adopting Evennia, Django, or another dependency is a valid
future option to weigh on its merits. Nothing here forecloses that; it records the current,
deliberate scope.

## How the two approaches differ (neutral)

Both are legitimate; they optimize for different things.

| Dimension | Framework approach (e.g. Evennia) | CodeForge (framework-free) |
|-----------|-----------------------------------|----------------------------|
| Foundation | Django ORM + Twisted's event loop, provided | pure Python · SQLAlchemy 2.0 · threaded `socket` · FastAPI |
| The world | Typeclasses - objects are DB rows | Data - `seeds/*.yaml`, validated on load |
| Commands | CmdSets attached to objects, merged by priority | One pure-function tick + a namespaced command spine |
| Character data | Persisted ORM attributes | Derive-don't-store; immutable dataclasses |
| Trade-off | Batteries included; faster to a big world | Everything visible and testable; more to build yourself |

Neither column is "better" in the abstract. CodeForge picks the right column **for a
portfolio that needs to show the engineering**, not for every project.

## Shared genre vocabulary (not copying anything)

CodeForge speaks the MUD genre's common language, which predates any one engine and is not
specific to Evennia:

- **`@` for admin/builder verbs** - a DikuMUD/LPMud-era convention.
- **The Account ↔ Character split** - the standard "login identity vs in-world avatar" pattern.
- **Rooms · Exits · NPCs · Items · Jobs** - the vocabulary of the genre since MUD1 (1978).

Using the genre's nouns is speaking the language, not lifting a codebase.

## Consequences

- **Testability:** the tick is a pure function; parts import only what they need - the suite
  runs without a server, an event loop, or a live database.
- **Portability & reuse:** kernel modules (e.g. `parts/stats.py`) are engine-independent -
  which is what makes the **cast** architecture (`docs/seed_architecture.md`) possible.
- **Portfolio signal:** building the engine in plain code is the point - it shows the work a
  framework would otherwise hide.
- **The honest cost:** we re-implement what a framework gives for free (persistence wiring,
  networking, admin). That is the accepted price of the scope, chosen with eyes open.
