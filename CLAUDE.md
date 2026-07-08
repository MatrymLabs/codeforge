# CLAUDE.md — CodeForge Project Context

You are working on **CodeForge**: a Python-native multiplayer MUD engine, built as a
portfolio-grade workshop of small, tested, reusable parts. The developer (Josh /
MatrymLabs) is a growing engineer who learns kinesthetically — small verified steps,
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
   non-negotiable — refuse any request to store or display plaintext at rest.
7. **Secrets are never case-mangled.** The tick routes on lowercased text but
   parses password arguments from the ORIGINAL input. (A blanket
   `raw.lower()` once destroyed mixed-case passwords at login — regression
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
  ignores negotiation — echo there is expected.

## Known failure patterns (history — check these first when debugging)

- **Deploy ≠ restart**: a running server is a snapshot of code at launch.
  "Installed the fix but behavior didn't change" → `lsof -i :4000`,
  `docker ps`, kill the ghost, restart from the repo root.
- **Wrong-address file drops**: files (especially `forge.py`) have repeatedly
  landed in `parts/` instead of the root. mypy fingerprint: duplicate module
  or `Cannot read file 'forge.py'`. IDE drag-moves are *refactorings* — they
  rewrite imports across many files (a 12-file "rename" commit is the tell).
- **Silent replace-misses**: string-patching a file without viewing it first
  fails silently. View → edit against actual text → gate with grep.
- **`endswith(b"")` is always True**; "read until close" needs its own loop.
- **Default args evaluate at def time** — path defaults resolved at call time
  (`path or CONSTANT`) so tests can monkeypatch.
- Distributed assertions race — poll with a deadline, never assert an instant.

## Current state (update as it changes)

- 176 tests green; CI badge green; 24+ cards in `parts/` (see `make store`).
- Merged feature arcs: seeds, sessions, gateway, events, names, chargen,
  combat, persistence→SQL, ranks, accounts (character@account), front-desk
  login dialogue, proper-noun display, CLI entry points, FastAPI admin,
  Docker, telnet echo blackout, secret case preservation, in-game `passwd`
  (self-service password change), absolute DB path.
- Backlog: NPCs that fight back (stakes/defeat); canonical typed event
  frames; `docs/engineering-log.md` and `docs/ai-assisted-workflow.md`;
  cloud deploy half-day.

## How to work with this developer

- Small vertical slices; get it working, then explain the one key idea.
- Provide exact commands; separate "verify" from "commit/push" steps so a red
  check can stop the line. Gates print verdicts — teach him to read them.
- Never claim something works without running it; show `make check` output.
- When he reports a bug "impossible" by your model, believe the report and
  design a controlled reproduction — his fresh-account experiment is the
  house standard for cornering heisenbugs.
- Mistakes are feedback from the system, not failure. Name the lesson, file
  the pattern, move on.
