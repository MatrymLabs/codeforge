# Contributing to CodeForge

## Setup

```bash
git clone git@github.com:MatrymLabs/codeforge.git && cd codeforge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make check   # everything green before you start
```

## The workshop rules

1. **Every part is a card.** One module in `parts/`, one clear job, a `CARD:` first
   docstring line, and a test twin in `tests/` (`parts/x.py` -> `tests/test_x.py`).
2. **New commands get a tick test.** A feature isn't wired until
   `handle_command(session, "...")` proves a player can reach it.
3. **The world is data.** Content belongs in `seeds/`, validated by loader gates --
   never hard-coded in Python.
4. **State is canonical; text is a projection.** Renderers and broadcasts must never
   mutate world state.
5. **One-Button Rule.** Any tool worth keeping gets a Makefile target
   (verbs DO: `fix`, `ship`; nouns SHOW: `world`, `store`).

## The ritual

```bash
make fix       # while working
make check     # before committing: lint, mypy, full suite
git commit -m "feat: <card> - <what it adds>"   # Conventional Commits
make ship      # check + refuse dirty tree + push
```

Commit types in use: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.

## Verification culture

- Files are judged by gates (`grep -c`, test counts), never by eyeballs.
- Error messages are version fingerprints: identical errors mean identical files.
- Tests must never touch real save files -- `conftest.py` quarantines
  `characters.json` and `accounts.json` into tmp for every test.

## Onboarding checklist

- [ ] Clone, set up, and get `make check` green
- [ ] Run `codeforge play`, walk to the library, take the key, unlock the door
- [ ] Run `spark`, connect twice with `nc localhost 4000`, watch the broadcasts
- [ ] Read `make store` and pick one card + twin to read end to end
- [ ] Make a tiny docs PR before a code PR
