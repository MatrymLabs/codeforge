# CLAUDE.md - CodeForge Project Context

You are working on **CodeForge**: a Python-native multiplayer MUD engine, built as a
portfolio-grade workshop of small, tested, reusable parts. The developer (Josh /
MatrymLabs) is a growing engineer who learns kinesthetically - small verified steps,
working code before theory, one concept at a time.

## What this is

- Classic MUD soul: ASCII splash, rooms, exits, items, locked doors, NPCs, callings
  (jobs), XP/leveling, combat, wizards, a training dummy that reassembles itself.
- Modern body: pure-function engine tick, threaded TCP gateway with a login front
  desk, account auth (salted pbkdf2), SQLite via SQLAlchemy 2.0, FastAPI admin
  surface, Docker image, event bus, YAML-seeded worlds, CI on GitHub Actions.
- Entry points: `spark` (server), `codeforge {serve,play,grant,migrate,migrate-db,passwd}`.

## Architecture laws (do not violate)

1. **State is canonical; text is a projection.** Renderers and broadcasts never
   mutate world state. Only validated engine logic mutates.
2. **The world is data.** Content lives in `seeds/*.yaml` (+ `splash.txt`),
   validated by loader gates in `parts/seed.py`. Never hard-code content in Python.
3. **Derive, don't store.** Character records persist minimal facts (job, level,
   xp, location, rank, account); stats/resources recompute on restore. A parity
   test pins restore-math == play-math.
4. **The engine tick is the only door.** `handle_command(session, text) -> str`
   in `forge.py`. All drivers (terminal loop, TCP gateway, future gateways) are
   thin callers. The gateway's login dialogue only *assembles* tick commands.
5. **Authorization before capability.** `@`-verbs check rank via `parts/ranks.py`
   before any code runs. HTTP admin mutations require owner-account Basic auth.
6. **Passwords are NEVER stored or logged in plaintext.** Accounts hold salted
   pbkdf2-sha256 (600k iterations); comparison is constant-time. This is
   non-negotiable - refuse any request to store or display plaintext at rest.
7. **Secrets are never case-mangled.** The tick routes on lowercased text but
   parses password arguments from the ORIGINAL input. (A blanket
   `raw.lower()` once destroyed mixed-case passwords at login - regression
   tests pin this forever. Never reintroduce it.)

## Conventions

- **Cards**: every module in `parts/` has a first-docstring-line `CARD: name -- purpose`
  and a test twin `tests/test_<name>.py`. New commands additionally get an
  engine-tick test (a feature isn't wired until `handle_command` proves reachable).
- **Labels**: identity strings are `lowercase_snake_case`, unique, permanent.
  Display capitalization happens only at render time via `display_name()`.
- **Makefile buttons**: verbs DO (`fix`, `check`, `ship`, `serve`, `unskew`),
  nouns SHOW (`world`, `store`). Anything used twice becomes a target.
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- **Test data must include hostile cases**: mixed case, symbols, near-misses.
  An all-lowercase suite once hid a password-destroying bug for days.

## Workflow (follow exactly)

1. Work on a **branch** (`feat/...`, `fix/...`), never directly on main.
2. `make fix` while working; `make check` (ruff + mypy + pytest) must be
   fully green before any commit. **Red output = stop, do not commit or push.**
3. Show the developer the diff and the test count before committing.
4. Push branch → PR (template in `.github/`) → CI checks (`check` + `docker`
   jobs) green → merge → `git checkout main && git pull`.
5. Verify by gates, not eyeballs: after edits, grep for the changed symbol;
   after installs, run the suite. Identical error output = identical file
   (the fix didn't land).

## Environment facts

- Host: Raspberry Pi ("skynet"), aarch64 Ubuntu, Python 3.13, venv at `.venv`.
- `parts/db.py` `DB_PATH` defaults to an ABSOLUTE path anchored to the repo
  root (`_default_db_path()`), so the server opens the same `codeforge.db`
  no matter which directory it launches from. Override with `CODEFORGE_DB`
  (containers, a chosen data dir). This closed the old cwd-relative trap
  that silently created a second, empty database when run from the wrong place.
- `conftest.py` quarantines the database into tmp for every test. Tests must
  never touch real state files.
- Save/state files are gitignored: `codeforge.db`, `save.json`,
  `characters.json`, `accounts.json`, `*.kdbx`. Never commit them; check
  `git status` for stowaways before committing (it has happened).
- The gateway speaks telnet: IAC WILL/WONT ECHO blackout masks password
  prompts (`_ask_secret`, `_strip_telnet` in `parts/gateway.py`). Raw `nc`
  ignores negotiation - echo there is expected.

## Known failure patterns (history - check these first when debugging)

- **Deploy ≠ restart**: a running server is a snapshot of code at launch.
  "Installed the fix but behavior didn't change" → `lsof -i :4000`,
  `docker ps`, kill the ghost, restart from the repo root.
- **Wrong-address file drops**: files (especially `forge.py`) have repeatedly
  landed in `parts/` instead of the root. mypy fingerprint: duplicate module
  or `Cannot read file 'forge.py'`. IDE drag-moves are *refactorings* - they
  rewrite imports across many files (a 12-file "rename" commit is the tell).
- **Silent replace-misses**: string-patching a file without viewing it first
  fails silently. View → edit against actual text → gate with grep.
- **`endswith(b"")` is always True**; "read until close" needs its own loop.
- **Default args evaluate at def time** - path defaults resolved at call time
  (`path or CONSTANT`) so tests can monkeypatch.
- Distributed assertions race - poll with a deadline, never assert an instant.
- **A dead sink can crash a live command**: broadcasting to a room writes to
  every session's echo sink; one closed socket (`OSError: Bad file descriptor`)
  used to propagate and kill the *acting* player's command. Fix: the event bus
  swallows + prunes a raising sink, and `_serve_player` unbinds its session in a
  `finally` even if the front desk raises. Never let a health-check connect the
  live gateway (it spawns a real session) - wait on the log line instead.
- **Interactive-only heisenbugs need a PTY**: a bug that vanishes when you run
  the client directly but bites through `make → bash → backgrounded server`
  needs `pty.fork` to reproduce (process-group / `SIGTTOU` / termios effects
  don't show under a pipe). The server log's `BrokenPipeError` tells you which
  side closed first (the peer did).

## Current state (update as it changes)

- 201 tests green; CI (`check` + `docker`) green; 23 cards in `parts/` (see
  `make store`).
- Merged feature arcs: seeds, sessions, gateway, events, names, chargen,
  combat, persistence→SQL, ranks, accounts (character@account), front-desk
  login dialogue, proper-noun display, CLI entry points, FastAPI admin,
  Docker image (real, on main, with a `docker` CI smoke-test), telnet echo
  blackout, secret case preservation, in-game `passwd` (self-service password
  change), absolute DB path, event-bus dead-sink resilience, the one-command
  **ritual** (`make ritual` / `ritual-down`) with a bundled password-masking
  client, security hardening (output sanitization, per-IP turnaway ledger, seat
  cap + idle timeouts, 8-char password floor - see `docs/reports/security/`).
- Backlog: NPCs that fight back (stakes/defeat); canonical typed event
  frames; `docs/engineering-log.md` and `docs/ai-assisted-workflow.md`;
  cloud deploy half-day.

## How to work with this developer

- Small vertical slices; get it working, then explain the one key idea.
- Provide exact commands; separate "verify" from "commit/push" steps so a red
  check can stop the line. Gates print verdicts - teach him to read them.
- Never claim something works without running it; show `make check` output.
- When he reports a bug "impossible" by your model, believe the report and
  design a controlled reproduction - his fresh-account experiment is the
  house standard for cornering heisenbugs.
- Mistakes are feedback from the system, not failure. Name the lesson, file
  the pattern, move on.

## Code identity & style (the forge voice)

CodeForge's code should physically read like the developer's imagination: part
inventor's workshop (invention, forged tools), part detective's case room (clues,
traces, deductions, case files), part tower-climb (worlds, gates, floors, skills,
quests, progression), all wound through a spiral motif (seeds becoming systems,
loops becoming layers). The names already in this repo - `spark`, `Forge`,
`Session`, `seed`, `handle_command` as the tick - are the seed of that voice.
Extend it; don't fight it.

**Signature vocabulary (reach for these over generic names):**
- Nouns: Forge, Spark, Core, Kiln, Seed, Spiral, Gate, Echo, Signal, Trace,
  CaseFile, Archive, Floor, Skill, Quest, Avatar, Engine, Compass, Lens,
  Keystone, Relic.
- Verbs: ignite, forge, trace, deduce, unlock, ascend, awaken, bind, inspect,
  map, evolve, attune, calibrate, enter, resolve.
- Architecture metaphors: Seed → Spark → Spiral → Forge → Gate → World;
  Clue → Trace → Deduction → CaseFile → Verdict; Player → Skill → Quest →
  Floor → WorldState.

**Shape the code surface, not just comments:** prefer memorable names for new
classes, functions, locals, and section dividers. Banish generic names -
`manager`, `handler`, `processor`, `data`, `item`, `thing`, `result` - in favor
of something with a face. When introducing a new module or subsystem, name it in
the voice (a diagnostics reader is a `Lens`, a validated installer is a `Gate`).

**When asked to restyle existing code, respond in this format:** Identity Read
(what it feels like now) → Style Map (generic → personal, e.g.
`validate_password → inspect_passkey`) → Transformed Code → Why It Feels Like Me
→ Safety Check (what you refused to rename and why).

### Governing boundaries (the style serves the engine, never the reverse)

These are hard limits. Creative naming stops at anything the system persists,
loads, or tests against:

1. **Behavior is preserved unless a redesign is explicitly requested.** A restyle
   is a rename, never a rewrite of logic.
2. **`make check` (ruff + mypy + pytest) must be green before any restyle is
   committed.** A rename that breaks an import or a test isn't done. When
   renaming a symbol used across files, update every caller and its test twin in
   the same change, then run the ritual.
3. **Persisted identifiers are FROZEN - never restyle them:** `lowercase_snake_case`
   labels (room/item/npc/job keys), YAML seed keys, database column names, JSON
   record keys, account/character handle formats, CARD docstring names, and CLI
   verb strings (`serve`, `play`, `grant`, `migrate`, `passwd`). Renaming these
   breaks save files, seeds, migrations, or the public interface. The metaphor
   lives in the *code*, not in the *data contract*.
4. **Never rename** `__init__`, `__str__`, `main`, dunder methods, pytest test
   function names, or third-party API symbols (FastAPI decorators, SQLAlchemy
   mapped attributes) unless provably safe.
5. **Clarity outranks poetry.** If a name makes the purpose unclear, it's wrong -
   `inspect_passkey` is good; `attune_the_arcane_ward` is not. Every reader,
   including a future teammate, must still understand what the code does.
6. Security and architecture laws above are never traded for style: no plaintext
   passwords, no lowercased secrets, canonical state stays canonical, however
   the variables are named.
