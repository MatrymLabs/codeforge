#!/usr/bin/env bash
# The Ritual -- bring the whole workshop online in one breath.
#
#   1. IGNITION   the gates run; a red gate stops the ritual (the forge never
#                 lights on broken code).
#   2. MIRROR     sync with GitHub -- fast-forward what's behind, name what's
#                 ahead. Never force, never silently push.
#   3. THE FORGE  light the gateway (the multiplayer server) and wait for it to
#                 announce itself.
#   4. THE GATE   open the MUD window at the front desk, ready to log in.
#
# When you walk away (quit / Ctrl-C), the forge banks its coals: a server the
# ritual lit is a server the ritual puts out. A forge already burning is left be.
set -euo pipefail

# --- Resolve the repo root from this script's own location -----------------
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

PORT=4000
SEED="${FORGE_SEED:-first-forge}"

# --- A little light (colour only when writing to a real terminal) ----------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'
  YELLOW=$'\033[33m'; CYAN=$'\033[36m'; OFF=$'\033[0m'
else
  BOLD=""; DIM=""; GREEN=""; RED=""; YELLOW=""; CYAN=""; OFF=""
fi
spark_line() { printf '%b⚒  %s%b\n' "$CYAN" "$1" "$OFF"; }
ok()   { printf '%b   ✓ %s%b\n' "$GREEN"  "$1" "$OFF"; }
warn() { printf '%b   ! %s%b\n' "$YELLOW" "$1" "$OFF"; }
die()  { printf '%b   ✗ %s%b\n' "$RED"    "$1" "$OFF"; exit 1; }

printf '\n%b=== T H E   R I T U A L ===%b   %bseed: %s%b\n\n' "$BOLD" "$OFF" "$DIM" "$SEED" "$OFF"

# --- Make the venv's tools reachable (spark / codeforge / make gates) -------
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  die "No .venv found. Run 'make env' first, then start the ritual."
fi

# --- 1. IGNITION: the gates -------------------------------------------------
spark_line "Ignition -- running the gates (lint · types · tests)..."
if make check >/tmp/ritual-check.log 2>&1; then
  ok "All gates green. $(grep -Eo '[0-9]+ passed' /tmp/ritual-check.log | tail -1 | sed 's/passed/tests passed/')"
else
  printf '%b' "$DIM"; tail -20 /tmp/ritual-check.log; printf '%b' "$OFF"
  die "A gate is red -- the forge stays cold. Fix it (see /tmp/ritual-check.log), then start the ritual again."
fi

# --- 2. MIRROR: sync with GitHub -------------------------------------------
spark_line "Mirror -- syncing with GitHub..."
if git rev-parse --abbrev-ref @'{u}' >/dev/null 2>&1; then
  git fetch --quiet origin || warn "Could not reach GitHub (offline?). Skipping mirror."
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  LOCAL="$(git rev-parse @)"; REMOTE="$(git rev-parse @'{u}')"; BASE="$(git merge-base @ @'{u}')"
  if [ -n "$(git status --porcelain)" ]; then
    warn "Working tree is dirty on '$BRANCH' -- leaving it untouched (nothing pulled or pushed)."
  elif [ "$LOCAL" = "$REMOTE" ]; then
    ok "In sync with origin/$BRANCH."
  elif [ "$LOCAL" = "$BASE" ]; then
    git merge --ff-only --quiet @'{u}' && ok "Fast-forwarded '$BRANCH' to match GitHub."
  elif [ "$REMOTE" = "$BASE" ]; then
    warn "'$BRANCH' is ahead by $(git rev-list --count @'{u}'..@) commit(s) -- unpushed. Review, then: git push"
  else
    warn "'$BRANCH' has diverged from GitHub. Reconcile by hand (the ritual never force-syncs)."
  fi
else
  warn "Branch '$(git rev-parse --abbrev-ref HEAD)' has no upstream -- skipping mirror."
fi

# Is the gateway accepting connections on :$PORT right now?
forge_is_up() { (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && { exec 3>&- 2>/dev/null; return 0; }; return 1; }

# When we leave, put out only a fire we started. Installed BEFORE we light the
# forge so any later failure still banks the coals -- no leaked servers.
STARTED_HERE=0
FORGE_PID=""
extinguish() {
  if [ "$STARTED_HERE" = "1" ] && [ -n "$FORGE_PID" ] && kill -0 "$FORGE_PID" 2>/dev/null; then
    printf '\n%b⚒  The forge banks its coals. Your deeds are remembered.%b\n' "$CYAN" "$OFF"
    kill "$FORGE_PID" 2>/dev/null || true
  elif [ "$STARTED_HERE" = "0" ]; then
    printf '\n%b⚒  Ritual closed. The forge you joined burns on.%b\n' "$CYAN" "$OFF"
  fi
}
trap extinguish EXIT INT TERM

# --- 3. THE FORGE: light the gateway ---------------------------------------
spark_line "The Forge -- lighting the gateway on :$PORT..."
if forge_is_up; then
  ok "A forge is already burning on :$PORT -- joining it (won't disturb it on exit)."
else
  FORGE_SEED="$SEED" spark >/tmp/ritual-spark.log 2>&1 &
  FORGE_PID=$!
  STARTED_HERE=1
  # Wait until the socket actually accepts a connection -- probe the port, don't
  # scrape the log (Python block-buffers stdout to a file; the bind is the truth).
  for _ in $(seq 1 60); do
    if forge_is_up; then break; fi
    if ! kill -0 "$FORGE_PID" 2>/dev/null; then
      printf '%b' "$DIM"; cat /tmp/ritual-spark.log; printf '%b' "$OFF"
      die "The forge failed to light (see above)."
    fi
    sleep 0.25
  done
  forge_is_up || die "The forge did not open :$PORT in time."
  ok "The forge is lit (pid $FORGE_PID) -- '$SEED' is live on :$PORT."
fi

# --- 4. THE GATE: open the MUD window --------------------------------------
spark_line "The Gate -- opening the MUD window (log in at the front desk)..."
printf '%b   Character (character@account), NEW, or GUEST awaits. Ctrl-C or QUIT to leave.%b\n\n' "$DIM" "$OFF"
sleep 0.4
if command -v telnet >/dev/null 2>&1; then
  telnet 127.0.0.1 "$PORT"          # telnet honours the password blackout
elif command -v nc >/dev/null 2>&1; then
  nc 127.0.0.1 "$PORT"              # nc works too (password echo is visible -- see docs/RUNNING.md)
else
  warn "No telnet or nc found. The forge is lit on :$PORT -- connect with a MUD client (Mudlet)."
  warn "Press Ctrl-C here to end the ritual and bank the forge."
  # Keep the ritual (and the server) alive until the operator ends it.
  while [ "$STARTED_HERE" = "1" ] && kill -0 "${FORGE_PID:-0}" 2>/dev/null; do sleep 1; done
fi
