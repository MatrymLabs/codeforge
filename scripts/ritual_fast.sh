#!/usr/bin/env bash
# The Ritual, Fast -- the ~1s preflight: is it safe to enter and code RIGHT NOW?
#
# Read-only. Runs only the instant, critical signals -- no test suite, no network, no
# security scans. CRITICAL checks GATE (red); QUALITY checks WARN (yellow). Before a
# push, a demo, or a portfolio check, run the full `make ritual` (standard) or the deep
# battery. This is the daily "let me code" door, not the launch checklist.
#
# Gate: green = enter · yellow = enter with warnings · red = fix first (exit 1).
set -uo pipefail   # deliberately NOT -e: run every check, then summarize the gate.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/lib.sh
source "$HERE/lib.sh"
[ -f ".venv/bin/activate" ] && source .venv/bin/activate

printf '\n%b=== R I T U A L  ·  F A S T ===%b   %b~1s preflight (read-only)%b\n\n' \
  "$BOLD" "$OFF" "$DIM" "$OFF"

# Counters are named to NOT collide with the RED/YELLOW colour vars from lib.sh.
BLOCKERS=0
WARNINGS=0

# --- CRITICAL (red): the environment must be sound to enter --------------------
spark_line "Imports -- compile the engine (fail fast before anything heavy)..."
if python -c "import forge, parts.registry, parts.gateway, parts.commands" 2>/tmp/rfast-imports.log; then
  ok "Engine imports clean."
else
  printf '%b' "$DIM"; tail -5 /tmp/rfast-imports.log; printf '%b' "$OFF"
  warn "Import/compile FAILED -- do not enter until fixed."
  BLOCKERS=$((BLOCKERS + 1))
fi

spark_line "Registry -- core classification loads and validates..."
if python -c "import sys; from parts.registry import load_collective, validate; sys.exit(1 if validate(load_collective()) else 0)" 2>/dev/null; then
  ok "Registry validates."
else
  warn "Registry INVALID -- the world will not load right."
  BLOCKERS=$((BLOCKERS + 1))
fi

# --- QUALITY (yellow): you can code, but know these ---------------------------
spark_line "Lint + types (quality, non-blocking)..."
if ruff check . >/dev/null 2>&1; then ok "Lint clean."; else warn "Lint has findings (make fix)."; WARNINGS=$((WARNINGS + 1)); fi
if mypy parts forge.py >/dev/null 2>&1; then ok "Types clean."; else warn "Type findings (make typecheck)."; WARNINGS=$((WARNINGS + 1)); fi

spark_line "Truth -- the project's claims still match reality..."
if make truth >/dev/null 2>&1; then ok "Claims verified (VeritasGate)."; else warn "A claim is FLAGGED (make truth)."; WARNINGS=$((WARNINGS + 1)); fi

spark_line "Workspace -- git state (informational)..."
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
DIRTY="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
ok "On '$BRANCH' -- $DIRTY uncommitted file(s)."

# --- THE GATE -----------------------------------------------------------------
echo ""
if [ "$BLOCKERS" -gt 0 ]; then
  printf '%b⛔ RED -- do not enter the MUD coding session (%s blocker(s)). Fix, then rerun.%b\n\n' \
    "$RED" "$BLOCKERS" "$OFF"
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  printf '%b🟡 YELLOW -- safe to code, with %s warning(s). Run `make ritual` before a push.%b\n\n' \
    "$YELLOW" "$WARNINGS" "$OFF"
  exit 0
else
  printf '%b🟢 GREEN -- safe to enter and code. Run `make ritual` / `-deep` before a push or demo.%b\n\n' \
    "$GREEN" "$OFF"
  exit 0
fi
