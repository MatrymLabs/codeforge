# The Shutdown Ritual

*One command secures the workshop at day's end - banks the forge, accounts for the
day's work honestly, and closes the after-action record.*

Bound to the phrase **"complete the ritual"** (`scripts/ritual_down.sh`). It is the mirror
of the [Startup Ritual](startup_ritual.md) (`scripts/ritual.sh`). It is **idempotent** -
run it twice and the second run just confirms all is cold.

## The phases

| # | Phase | What it does |
|---|-------|--------------|
| 1 | **BANK THE FORGE** | Stop any gateway still burning on `:4000` (a server the startup ritual lit and detached, or a ghost from an old launch) and stop any codeforge containers. `start the ritual` banks the forge *it* lit when you quit; this catches everything else. |
| 2 | **MUSTER** | An honest end-of-day report: uncommitted changes, unpushed commits. It **never pushes for you** - it tells the truth and leaves the decision to you. |
| 3 | **PUSH READINESS** | Names every blocker and reports `commit_ready` / `push_ready`. Fast blockers always run; the full gate runs only when there are unpushed commits to protect. **It never pushes** - it tells you loudly *not* to when something is wrong. |
| 3b | **DOCS IMPACT** | Informational nudge: if the about-to-leave set (uncommitted + unpushed) touches code (`parts/*.py`, `forge.py`, `scripts/*`) but no `CHANGELOG`/`README`/`docs/`, it warns to review docs impact before pushing. Never blocks. |
| 4 | **CLOSE THE RECORD** | Stamps the day's after-action record (`reports/ritual/<date>.md`) with the closing state - tree, unpushed count, and the commit/push-ready verdict - so the day is auditable start to finish. |
| 5 | **DOUSE THE EMBERS** | Clear the ritual's scratch logs from `/tmp`. |

## The push-readiness gate

`commit_ready` and `push_ready` are `yes`/`NO` verdicts. A blocker flips them to `NO` and
names itself - it does **not** push (the ritual never pushes for you), it makes the unsafe
choice loud. Block conditions:

| Blocker | Affects | Check |
|---------|---------|-------|
| A `.env` file is staged | commit + push | staged-path scan |
| A generated/state file is staged (`*.db`, `save/characters/accounts.json`, `coverage.xml`, `*.kdbx`) | commit + push | staged-path scan |
| A committed secret | commit + push | `detect-secrets` vs the baseline |
| Broken imports | commit + push | `python -c "import forge"` |
| Red gates (tests/lint/types/coverage) | push | `make check` - **only when there are unpushed commits** (change-aware; skipped when there is nothing to push) |

## What it is, and is not

- It **reports and blocks by advice**; it does not push, commit, or force anything. The
  ritual never pushes for you - it makes the unsafe choice loud.
- The gate is **change-aware**: the expensive `make check` runs only when unpushed commits
  exist, so a clean shutdown stays fast.
- It shares one voice with the other ceremonies via `scripts/lib.sh` (colours + message
  helpers), so startup and shutdown read as one system.

## Related

- [The Startup Ritual](startup_ritual.md) - the mirror ceremony (and its fast/standard modes).
- [VeritasGate](veritas.md) - the `truth check` the shutdown gate will consult.
- [Repo integrity](repo_integrity.md) - the composite health report.
