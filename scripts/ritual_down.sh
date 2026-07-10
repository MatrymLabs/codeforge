#!/usr/bin/env bash
# The Ritual, Closed -- secure the workshop at day's end.
#
#   1. BANK THE FORGE   stop any gateway still burning on :4000 (started detached,
#                       or a ghost from an old launch) and stop codeforge
#                       containers. `start the ritual` banks the forge it lit when
#                       you quit; this catches everything else.
#   2. MUSTER           an honest end-of-day report: uncommitted work, unpushed
#                       commits. It never pushes for you -- it just tells the truth.
#   3. PUSH READINESS   is it safe to commit and push? Names every blocker (staged
#                       .env / generated files, committed secrets, broken imports,
#                       red gates) and reports commit_ready / push_ready. Never pushes.
#   4. CLOSE THE RECORD stamp the day's after-action file with the closing state.
#   5. DOUSE THE EMBERS clear the ritual's scratch logs.
#
# Idempotent: run it twice and the second run just confirms all is cold.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
# The push-readiness checks need the venv's tools (detect-secrets, pytest via make).
[ -f ".venv/bin/activate" ] && source .venv/bin/activate

PORT=4000

# shellcheck source=scripts/lib.sh
source "$HERE/lib.sh"

printf '\n%b=== T H E   R I T U A L ,   C L O S E D ===%b\n\n' "$BOLD" "$OFF"

# --- Who is listening on :$PORT? (lsof, else ss) ---------------------------
forge_pids() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:$PORT" 2>/dev/null || true
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnpH 2>/dev/null | grep ":$PORT[[:space:]]" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true
  fi
}

# --- 1. BANK THE FORGE -----------------------------------------------------
step "Banking the forge -- looking for a gateway on :$PORT..."
pids="$(forge_pids)"
if [ -n "$pids" ]; then
  for pid in $pids; do
    kill "$pid" 2>/dev/null && ok "Extinguished gateway pid $pid." || warn "Could not stop pid $pid (already gone?)."
  done
  sleep 1
  [ -z "$(forge_pids)" ] && ok "Port :$PORT is clear." || warn "Something still holds :$PORT -- check by hand (lsof -i :$PORT)."
else
  ok "No forge burning on :$PORT."
fi

# Stop any codeforge containers (best-effort; skip quietly if docker is absent).
if command -v docker >/dev/null 2>&1; then
  step "Banking containers -- stopping any codeforge image..."
  ids="$(docker ps -q --filter ancestor=codeforge 2>/dev/null || true)"
  if [ -n "$ids" ]; then
    docker stop $ids >/dev/null 2>&1 && ok "Stopped $(echo "$ids" | wc -l | tr -d ' ') container(s)." || warn "Could not stop some containers."
  else
    ok "No codeforge containers running."
  fi
fi

# --- 2. MUSTER: the honest end-of-day report -------------------------------
step "Muster -- accounting for the day's work..."
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  warn "Uncommitted changes on '$BRANCH' -- commit them before you rest:"
  printf '%b' "$DIM"; git status --short; printf '%b' "$OFF"
else
  ok "Working tree clean on '$BRANCH'."
fi
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  ahead="$(git rev-list --count '@{u}'..@ 2>/dev/null || echo 0)"
  if [ "$ahead" -gt 0 ]; then
    warn "'$BRANCH' is ahead by $ahead commit(s) -- unpushed. When ready: git push"
  else
    ok "Pushed and in sync with GitHub."
  fi
else
  warn "'$BRANCH' has no upstream -- push it to back up your work."
fi

# --- 3. PUSH READINESS: is it safe to commit and push? ---------------------
# Fast blockers always run; the full gate (make check) runs only when there are unpushed
# commits to protect. This REPORTS -- it never pushes. It tells you loudly NOT to when
# something is wrong. Block conditions: staged .env, staged generated/state files,
# committed secrets, broken imports, red gates.
step "Push readiness -- checking for blockers before you push..."
COMMIT_BLOCKERS=0
PUSH_BLOCKERS=0
STAGED="$(git diff --cached --name-only 2>/dev/null || true)"

if printf '%s\n' "$STAGED" | grep -qE '(^|/)\.env$'; then
  warn "A .env file is STAGED -- unstage it (secrets never enter git)."; COMMIT_BLOCKERS=$((COMMIT_BLOCKERS + 1))
fi
if printf '%s\n' "$STAGED" | grep -qE '\.(db|kdbx)$|(^|/)(save|characters|accounts)\.json$|(^|/)coverage\.xml$'; then
  warn "A generated/state file is STAGED (db · save · accounts · coverage) -- unstage it."; COMMIT_BLOCKERS=$((COMMIT_BLOCKERS + 1))
fi
if command -v detect-secrets-hook >/dev/null 2>&1; then
  if git ls-files | xargs detect-secrets-hook --baseline .secrets.baseline >/dev/null 2>&1; then
    ok "No committed secrets (detect-secrets)."
  else
    warn "detect-secrets flagged a tracked file -- audit before pushing."; COMMIT_BLOCKERS=$((COMMIT_BLOCKERS + 1))
  fi
else
  warn "detect-secrets not available -- secret scan SKIPPED (run 'make env')."
fi
if python -c "import forge" >/dev/null 2>&1; then
  ok "Engine imports compile."
else
  warn "Imports are BROKEN -- do not commit or push."; COMMIT_BLOCKERS=$((COMMIT_BLOCKERS + 1))
fi

PUSH_BLOCKERS=$COMMIT_BLOCKERS
AHEAD=0
git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1 && AHEAD="$(git rev-list --count '@{u}'..@ 2>/dev/null || echo 0)"
if [ "$AHEAD" -gt 0 ]; then
  if make check >/tmp/ritual-down-check.log 2>&1; then
    ok "Gates green (make check) -- $AHEAD commit(s) ready to push."
  else
    warn "Gates RED (make check) -- do not push. See /tmp/ritual-down-check.log."; PUSH_BLOCKERS=$((PUSH_BLOCKERS + 1))
  fi
fi

COMMIT_READY="yes"; [ "$COMMIT_BLOCKERS" -gt 0 ] && COMMIT_READY="NO"
PUSH_READY="yes"; [ "$PUSH_BLOCKERS" -gt 0 ] && PUSH_READY="NO"
if [ "$PUSH_BLOCKERS" -gt 0 ]; then
  warn "commit_ready: $COMMIT_READY · push_ready: $PUSH_READY ($PUSH_BLOCKERS blocker(s)) -- resolve before you push."
else
  ok "commit_ready: $COMMIT_READY · push_ready: $PUSH_READY."
fi

# --- 4. CLOSE THE RECORD: stamp the day's after-action file (if one exists) --
# Closes the loop begun at startup: the same dated record gets an honest end-of-day
# line -- tree state and unpushed count -- so the day is auditable start to finish.
REPORT_FILE="reports/ritual/$(date -u +%Y-%m-%d).md"
if [ -f "$REPORT_FILE" ]; then
  tree_state="clean"; [ -n "$(git status --porcelain 2>/dev/null)" ] && tree_state="DIRTY (uncommitted)"
  unpushed="0"; git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1 && unpushed="$(git rev-list --count '@{u}'..@ 2>/dev/null || echo 0)"
  {
    echo "## Ritual CLOSE $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "- tree: $tree_state · unpushed: $unpushed commit(s) on '$BRANCH'"
    echo "- commit_ready: $COMMIT_READY · push_ready: $PUSH_READY"
    echo ""
  } >> "$REPORT_FILE"
  ok "After-action record closed: $REPORT_FILE"
fi

# --- 5. DOUSE THE EMBERS ---------------------------------------------------
rm -f /tmp/ritual-spark.log /tmp/ritual-check.log /tmp/ritual-coverage.log /tmp/ritual-bandit.log \
      /tmp/ritual-audit.log /tmp/ritual-readiness.log /tmp/ritual-truth.log /tmp/ritual-secrets.log \
      /tmp/ritual-smoke.log /tmp/ritual-down-check.log 2>/dev/null || true

printf '\n%b⚒  The forge is cold. The workshop is secured. Rest well.%b\n\n' "$CYAN" "$OFF"
