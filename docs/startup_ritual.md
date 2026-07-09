# The Startup Ritual

*One command brings the whole workshop online — and refuses to light the forge on
anything broken, insecure, or internally inconsistent.*

Bound to the phrase **"start the ritual"** (`scripts/ritual.sh`). Its mirror,
**"complete the ritual"** (`scripts/ritual_down.sh`), secures the workshop at day's
end.

## The phases (each earlier gate must pass before the next runs)

| # | Phase | Gates? | What it does |
|---|-------|--------|--------------|
| 1 | **IGNITION** | **hard** | `make check` — lint · types · tests · property. A red gate stops the ritual. |
| 2 | **WARDS** | **hard (SAST)** | `bandit` GATES the forge (never run on a known SAST finding); `pip-audit` runs and **warns** (network best-effort — recover CVEs with `make patch`). |
| 3 | **READINESS** | **hard (registry)** | `make readiness` — the system audits itself: the **classification registry validates** (no duplicates, no orphans) and gates; the **project dashboard** (`pm status`, computed from the registry + QualityGate) prints as an informational readiness report. A YELLOW board is not a red gate — `watch` ≠ `fail`. |
| 4 | **MIRROR** | soft | Sync with GitHub — fast-forward what's behind, name what's ahead. Never force, never silently push. |
| 5 | **THE FORGE** | — | Light the multiplayer gateway on `:4000` and wait for it to announce itself. |
| 6 | **THE GATE** | — | Open the MUD window at the front desk, ready to log in. |

When you walk away, the forge **banks its coals**: a server the ritual lit is a
server the ritual puts out. A forge already burning is left alone.

## The close ritual (`complete the ritual`)

1. **BANK THE FORGE** — stop any gateway on `:4000` and any codeforge container.
2. **MUSTER** — an honest end-of-day report: uncommitted changes, unpushed commits. It never pushes for you.
3. **DOUSE THE EMBERS** — clear the ritual's scratch logs.

## Related one-button targets (the control panel)

- `make check` — the full gate (lint · types · tests · property).
- `make readiness` — registry validation + the project dashboard (used by phase 3; run it any time).
- `make security` — `bandit` + `pip-audit`.
- `make patch` — scan deps for CVEs → apply fixes → **re-run `make check`** → file dated evidence.
- `make daily` — `make patch`, then trigger the Federal Guidance Library's `library check`.
- `make doctor` — run the gates read-only, stop at the first failure, prescribe the fix.

## What the ritual does *not* yet check (backlog)

Per-domain health the Safety+QA prompt describes — **library** freshness at startup,
**classroom** quiz quit/resume coverage, and **hardware store** part docs/tests — are
tracked in `docs/project_management.md` and surfaced today by `qa gate all` /
`pm status`, but are not yet separate ritual phases.
