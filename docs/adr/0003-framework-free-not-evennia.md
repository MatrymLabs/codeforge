# ADR-0003: Framework-free — why CodeForge is not Evennia

**Status:** accepted

## Context

CodeForge's predecessor (`codeforge_mk1`, now the public `codeforge-evennia`) was built on
**Evennia** — a Python MUD framework layered on **Django** (ORM) and **Twisted** (async
reactor). That project ran, but its architecture imposed limits this project exists to
escape: the world lives in the database as **typeclassed** rows; behaviour is added by
subclassing deep model-backed hierarchies; commands are **CmdSets** attached to objects and
merged by priority; character data is arbitrary mutable **Attributes** persisted through the
ORM. Everything is coupled to the framework, so little can be tested — or reused — in
isolation. CodeForge is a deliberate, clean-room rewrite that keeps none of that.

## Decision

CodeForge is **framework-free** and stays that way. The following are laws, not preferences:

1. **No Evennia, no Django, no Twisted — ever.** No dependency on, import of, or vendored
   copy of any of them. The stack is pure Python + `sqlalchemy` + `fastapi` + `uvicorn` +
   `websockets` + `pyyaml`. Adding one of the forbidden frameworks is a rejected change.
2. **The world is data, not typeclasses.** Content lives in `seeds/*.yaml`, validated by
   loader gates — never as ORM models bolted to Python classes. State is canonical; text is
   a projection (ADR-0001).
3. **One pure-function tick, not CmdSets.** `handle_command(session, signal) -> str` is the
   only door. No command sets attached to objects, no priority-merge machinery. The command
   spine namespaces verbs (`CORE` / `ADMIN @` / `SEED`) in plain, testable code.
4. **Derive, don't store (ADR-0002).** Character records persist minimal facts; stats and
   resources are immutable, validated dataclasses that import nothing from the engine — the
   opposite of Evennia's mutable, DB-backed Attributes. Kernel modules stay portable.
5. **Small tested reusable parts, not a monolith.** Every module in `parts/` has one job, a
   `CARD:` line, and a test twin. Extension is composition, not subclassing a framework.

## What Evennia does vs what CodeForge does

| Dimension | Evennia (left behind) | CodeForge |
|-----------|-----------------------|-----------|
| Foundation | Django ORM + Twisted reactor | pure Python · SQLAlchemy 2.0 · threaded `socket` · FastAPI |
| The world | Typeclasses — every object is a DB row | Data — `seeds/*.yaml`, validated on load |
| Commands | CmdSets attached to objects, merged by priority | One pure-function tick + a namespaced command spine |
| Character data | Mutable `Attributes` persisted via the ORM | Derive-don't-store; immutable validated dataclasses |
| Web surface | Django admin + website | FastAPI admin surface |
| Extension | Subclass model-backed typeclasses | Compose small, tested `parts/` |

## What is NOT copying (genre-universal, explicitly allowed)

Sharing the MUD genre's common language is not copying an engine. These predate Evennia and
are permitted:

- **`@` for admin/builder verbs** — a DikuMUD/LPMud-era convention, decades old.
- **The Account ↔ Character split** — the standard "login identity vs in-world avatar"
  pattern across modern MUDs.
- **Rooms · Exits · NPCs · Items · Jobs** — the vocabulary of the genre since MUD1 (1978).

Using the genre's nouns is speaking the language, not lifting a codebase.

## Consequences

- **Testability:** the tick is a pure function; parts import only what they need — the suite
  runs without a server, a reactor, or a live database. Evennia's coupling makes that hard.
- **Portability & reuse:** kernel modules (e.g. `parts/stats.py`) are engine-independent and
  drop into any project. This is what makes the **cast** architecture (ADR-forthcoming)
  possible at all.
- **Portfolio signal:** "I rejected the obvious framework and built a smaller, tested engine
  to escape its coupling" is a defensible engineering decision, backed by the code.
- **The cost, honestly:** we re-implement what Evennia gives for free (persistence wiring,
  networking, admin). That is the accepted price of owning the architecture and its limits.

## Verification (how we know, and how to re-check)

Proven 2026-07-10 by an integrity sweep — **zero** matches for `evennia|django|twisted|
typeclass|cmdset` in source, and no forbidden dependency in `pyproject.toml`. Re-run any time:

```bash
grep -rniE "evennia|from django|import django|twisted|typeclass|cmdset" parts/ forge.py scripts/
grep -iE "evennia|django|twisted" pyproject.toml
```

Either match returning a hit (outside an honest lineage note) is a regression against this ADR.
