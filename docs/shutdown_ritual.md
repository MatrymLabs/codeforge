# The Shutdown Ritual

*One command secures the workshop at day's end — banks the forge, accounts for the
day's work honestly, and closes the after-action record.*

Bound to the phrase **"complete the ritual"** (`scripts/ritual_down.sh`). It is the mirror
of the [Startup Ritual](startup_ritual.md) (`scripts/ritual.sh`). It is **idempotent** —
run it twice and the second run just confirms all is cold.

## The phases

| # | Phase | What it does |
|---|-------|--------------|
| 1 | **BANK THE FORGE** | Stop any gateway still burning on `:4000` (a server the startup ritual lit and detached, or a ghost from an old launch) and stop any codeforge containers. `start the ritual` banks the forge *it* lit when you quit; this catches everything else. |
| 2 | **MUSTER** | An honest end-of-day report: uncommitted changes, unpushed commits. It **never pushes for you** — it tells the truth and leaves the decision to you. |
| 3 | **CLOSE THE RECORD** | Stamps the day's after-action record (`reports/ritual/<date>.md`) with the closing state — tree clean/dirty, unpushed count — so the day is auditable start to finish. |
| 4 | **DOUSE THE EMBERS** | Clear the ritual's scratch logs from `/tmp`. |

## What it is, and is not

- It **reports**; it does not push, commit, or force anything. The muster is a checklist,
  not an autopilot.
- It shares one voice with the other ceremonies via `scripts/lib.sh` (colours + message
  helpers), so startup and shutdown read as one system.

## Roadmap (proposed — see the Automation Enhancement Audit)

A future batch adds a **commit/push-readiness gate** to the muster — `commit_ready` /
`push_ready` booleans that **block a push** when secrets are detected, tests fail, imports
are broken, or a `.env` is staged. Today the muster *reports* these conditions; the gate
would *enforce* them.

## Related

- [The Startup Ritual](startup_ritual.md) — the mirror ceremony (and its fast/standard modes).
- [VeritasGate](veritas.md) — the `truth check` the shutdown gate will consult.
- [Repo integrity](repo_integrity.md) — the composite health report.
