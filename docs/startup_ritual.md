# The Startup Ritual

*One command brings the whole workshop online — and refuses to light the forge on
anything broken, insecure, or internally inconsistent.*

Bound to the phrase **"start the ritual"** (`scripts/ritual.sh`). Its mirror,
**"complete the ritual"** (`scripts/ritual_down.sh`), secures the workshop at day's
end.

## The phases (each earlier gate must pass before the next runs)

| # | Phase | Gates? | What it does |
|---|-------|--------|--------------|
| 1 | **IGNITION** | **hard** | `make check` — lint · types · the full suite **with coverage** in one run (pytest `--cov` + threshold). One suite run, not two. Parity with CI. A red gate stops the ritual. |
| 2 | **WARDS** | **hard (SAST + secrets)** | `bandit` (SAST) and `detect-secrets` GATE the forge — it never lights on a known SAST finding or a committed secret; `pip-audit` runs and **warns** (network best-effort — recover CVEs with `make patch`). |
| 3 | **READINESS** | **hard (registry)** | `make readiness` — the classification registry validates (no duplicates, no orphans) and gates; the project dashboard (`pm status`) prints as an informational readiness report. `watch` ≠ `fail`. |
| 4 | **VERITAS** | **hard (claims)** | `make truth` — VeritasGate reads the project's own claims back against the code; a FLAGGED claim (overclaim, drift-prone count, missing doc, broken registry/board) gates. *No claim without correspondence.* |
| 5 | **MIRROR** | soft | Sync with GitHub — fast-forward what's behind, name what's ahead. Never force, never silently push. |
| 6 | **SMOKE** | **hard (acceptance)** | `make smoke` — the whole engine end to end over a live socket (log in · look · do · log out) *before* the door opens to a human. Its timing is banked as performance evidence. |
| 7 | **THE FORGE** | — | Light the multiplayer gateway on `:4000` and wait for it to announce itself. |
| 8 | **THE GATE** | — | Open the MUD window at the front desk, ready to log in. |

Every startup banks a dated **after-action record** under `reports/ritual/` — the gate
verdicts, test count, coverage, and smoke timing — traceable after the fact. When you walk
away, the forge **banks its coals**: a server the ritual lit is a server the ritual puts
out. A forge already burning is left alone.

## Ritual modes (run each check at the right altitude)

Not every check belongs on every boot. Pick the mode by the task:

| Mode | Command | Time | For |
|------|---------|------|-----|
| **fast** | `make ritual-fast` | **~1s** | The daily "let me code" door. Read-only. Critical checks (imports · registry · truth) GATE red; lint/types/claims WARN yellow. No suite, no network, no scans. |
| **standard** | `make ritual` (`start the ritual`) | ~45s | Full readiness: gates · security · registry · truth · smoke · light the forge · open the MUD. |
| **deep** | *(proposed)* | ~1min+ | Standard + `pip-audit` (network) + `sbom` + `repo-integrity` — before a push, demo, or portfolio check. |

**fast → green/yellow/red gate:** green = safe to enter and code · yellow = code with
warnings · red = fix a blocker (broken import, invalid registry) before entering. See the
Automation Enhancement Audit (proposed `docs/automation_system.md`) for the full mode design; deep mode lands in a later batch.

## The close ritual (`complete the ritual`)

See **[The Shutdown Ritual](shutdown_ritual.md)** — banks the forge, musters uncommitted /
unpushed work honestly, and closes the day's after-action record.

## Related one-button targets (the control panel)

- `make check` — the full gate (lint · types · tests · property).
- `make readiness` — registry validation + the project dashboard (used by phase 3; run it any time).
- `make security` — `bandit` + `pip-audit` + `make secrets` (detect-secrets).
- `make patch` — scan deps for CVEs → apply fixes → **re-run `make check`** → file dated evidence.
- `make daily` — `make patch`, then trigger the Federal Guidance Library's `library check`.
- `make doctor` — run the gates read-only, stop at the first failure, prescribe the fix.

## What the ritual does *not* yet check (backlog)

Per-domain health the Safety+QA prompt describes — **library** freshness at startup,
**classroom** quiz quit/resume coverage, and **hardware store** part docs/tests — are
tracked in `docs/project_management.md` and surfaced today by `qa gate all` /
`pm status`, but are not yet separate ritual phases.
