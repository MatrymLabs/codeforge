#!/usr/bin/env bash
# The Ritual -- bring the whole workshop online in one breath.
#
#   1. IGNITION   the gates run -- lint, types, tests AND the coverage threshold
#                 (parity with CI: the ritual gates on exactly what the pipeline
#                 gates on). A red gate stops the ritual; the forge never lights
#                 on broken code.
#   2. WARDS      security posture -- SAST (bandit) GATES the forge; a dependency
#                 CVE scan (pip-audit) runs and warns. Cyber/SSDF best practice:
#                 never run on code with a known SAST finding.
#   3. READINESS  the system audits itself -- registry validation GATES (a corrupt
#                 registry is a defect); the readiness dashboard (pm status) reports.
#   4. VERITAS    do the project's claims match reality? (VeritasGate / `truth
#                 check`). A FLAGGED claim -- an overclaim, a drift-prone count, a
#                 missing doc -- is a defect and GATES. No claim without correspondence.
#   5. MIRROR     sync with GitHub -- fast-forward what's behind, name what's
#                 ahead. Never force, never silently push.
#   6. SMOKE      prove the whole engine end-to-end (log in -> look -> do -> log
#                 out over a live socket) BEFORE opening the door to a human. The
#                 acceptance gate; its timing is banked as performance evidence.
#   7. THE FORGE  light the gateway (the multiplayer server) and wait for it to
#                 announce itself.
#   8. THE GATE   open the MUD window at the front desk, ready to log in.
#
# Every startup banks a dated after-action record under reports/ritual/ -- the
# gate verdicts, test count, coverage, and smoke timing, traceable after the fact.
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

# --- A little light + the shared voice (colours, spark_line/ok/warn/die) ----
# shellcheck source=scripts/lib.sh
source "$HERE/lib.sh"

printf '\n%b=== T H E   R I T U A L ===%b   %bseed: %s%b\n\n' "$BOLD" "$OFF" "$DIM" "$SEED" "$OFF"

# --- Make the venv's tools reachable (spark / codeforge / make gates) -------
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  die "No .venv found. Run 'make env' first, then start the ritual."
fi

# --- 1. IGNITION: the gates -- lint · types · full suite WITH coverage (one run) --
# `make check` folds coverage into a single suite run (no double execution), and enforces
# the threshold. Parity with CI, which runs the same `make check`.
IGN_TESTS=""; IGN_COV=""
spark_line "Ignition -- running the gates (lint · types · tests · coverage)..."
if make check >/tmp/ritual-check.log 2>&1; then
  IGN_TESTS="$(grep -Eo '[0-9]+ passed' /tmp/ritual-check.log | awk '{s+=$1} END{if(s)print s" passed"}')"
  IGN_COV="$(grep -Eo 'Total coverage: [0-9.]+%' /tmp/ritual-check.log | tail -1 | sed 's/Total coverage: //')"
  ok "All gates green. ${IGN_TESTS:-tests passed}${IGN_COV:+ · coverage $IGN_COV}."
else
  printf '%b' "$DIM"; tail -20 /tmp/ritual-check.log; printf '%b' "$OFF"
  die "A gate is red -- the forge stays cold. Fix it (see /tmp/ritual-check.log), then start the ritual again."
fi

# --- 2. WARDS: security posture (SAST + secrets gate; dependency CVEs warn) --
# Cyber/SSDF discipline: the forge never lights on code with a known SAST finding or a
# committed secret. bandit + detect-secrets are offline + fast, so they GATE; pip-audit
# needs the network, so it WARNS (recover CVEs with `make patch`).
spark_line "Wards -- checking security posture (SAST + secrets + dependency CVEs)..."
if bandit -c pyproject.toml -r parts forge.py -q >/tmp/ritual-bandit.log 2>&1; then
  ok "SAST clean (bandit)."
else
  printf '%b' "$DIM"; tail -20 /tmp/ritual-bandit.log; printf '%b' "$OFF"
  die "SAST found an issue -- the forge stays cold. Fix it (bandit), then start the ritual again."
fi
if git ls-files | xargs detect-secrets-hook --baseline .secrets.baseline >/tmp/ritual-secrets.log 2>&1; then
  ok "No secrets committed (detect-secrets)."
else
  printf '%b' "$DIM"; tail -12 /tmp/ritual-secrets.log; printf '%b' "$OFF"
  die "A secret was detected -- do NOT enter the MUD. Remove it (or audit the baseline), then restart."
fi
WARDS_AUDIT="clean"
if pip-audit --skip-editable >/tmp/ritual-audit.log 2>&1; then
  ok "No known dependency CVEs (pip-audit)."
else
  WARDS_AUDIT="findings or offline (review: make patch)"
  warn "pip-audit reported findings or was offline -- review with 'make patch' (see /tmp/ritual-audit.log)."
fi

# --- 3. READINESS: the global self-audit (registry gates; QA/PM report) -----
# "Is the system still healthy today?" -- registry validation GATES (a corrupt
# registry is a defect); the readiness dashboard (pm status) is informational
# (a YELLOW board is not a red gate -- watch != fail).
spark_line "Readiness -- the system audits itself (registry + QA + docs)..."
if make readiness >/tmp/ritual-readiness.log 2>&1; then
  ok "Registry validates. Readiness dashboard:"
  printf '%b' "$DIM"; sed 's/^/     /' /tmp/ritual-readiness.log; printf '%b' "$OFF"
else
  printf '%b' "$DIM"; tail -20 /tmp/ritual-readiness.log; printf '%b' "$OFF"
  die "Readiness check failed (registry invalid) -- fix it, then start the ritual again."
fi

# --- 4. VERITAS: do the project's claims match reality? (VeritasGate) --------
# Truth discipline: no claim without correspondence. A FLAGGED claim (an overclaim, a
# drift-prone hardcoded count, a missing doc, a broken registry/board) is a defect -- it
# GATES. This is the in-MUD `truth check`, run before the forge lights.
spark_line "Veritas -- checking the project's claims against reality (truth check)..."
if make truth >/tmp/ritual-truth.log 2>&1; then
  ok "All claims verified (VeritasGate)."
else
  printf '%b' "$DIM"; tail -24 /tmp/ritual-truth.log; printf '%b' "$OFF"
  die "A claim is FLAGGED -- correct the claim (or the code) before entering. See /tmp/ritual-truth.log."
fi

# --- 4b. INTEGRITY: file the dated repo-integrity evidence bundle ------------
# The RepoIntegrityRitual composes the same self-audit signals (registry, QA board,
# overclaim scan, docs, dependency provenance) into ONE dated, honest evidence file.
# Its gating signals already GATED above (readiness + truth); here we FILE the bundle,
# so "run the ritual" produces the integrity evidence too (it used to be skipped).
INTEGRITY_STATUS="filed"
spark_line "Integrity -- filing the dated repo-integrity evidence bundle..."
if make repo-integrity >/tmp/ritual-integrity.log 2>&1; then
  ok "Repo-integrity evidence filed."
else
  INTEGRITY_STATUS="report failed (see /tmp/ritual-integrity.log)"
  warn "repo-integrity could not file its report -- review /tmp/ritual-integrity.log."
fi

# --- 5. MIRROR: sync with GitHub -------------------------------------------
MIRROR_STATUS="unknown"
spark_line "Mirror -- syncing with GitHub..."
if git rev-parse --abbrev-ref @'{u}' >/dev/null 2>&1; then
  git fetch --quiet origin || warn "Could not reach GitHub (offline?). Skipping mirror."
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  LOCAL="$(git rev-parse @)"; REMOTE="$(git rev-parse @'{u}')"; BASE="$(git merge-base @ @'{u}')"
  if [ -n "$(git status --porcelain)" ]; then
    MIRROR_STATUS="dirty tree (untouched)"
    warn "Working tree is dirty on '$BRANCH' -- leaving it untouched (nothing pulled or pushed)."
  elif [ "$LOCAL" = "$REMOTE" ]; then
    MIRROR_STATUS="in sync"
    ok "In sync with origin/$BRANCH."
  elif [ "$LOCAL" = "$BASE" ]; then
    MIRROR_STATUS="fast-forwarded to origin"
    git merge --ff-only --quiet @'{u}' && ok "Fast-forwarded '$BRANCH' to match GitHub."
  elif [ "$REMOTE" = "$BASE" ]; then
    MIRROR_STATUS="ahead $(git rev-list --count @'{u}'..@) (unpushed)"
    warn "'$BRANCH' is ahead by $(git rev-list --count @'{u}'..@) commit(s) -- unpushed. Review, then ship the PR: make ship"
  else
    MIRROR_STATUS="diverged (reconcile by hand)"
    warn "'$BRANCH' has diverged from GitHub. Reconcile by hand (the ritual never force-syncs)."
  fi
else
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  MIRROR_STATUS="no upstream"
  warn "Branch '$BRANCH' has no upstream -- skipping mirror."
fi

# --- 6. SMOKE: prove the whole engine end-to-end before opening the door -----
# QA acceptance gate: log in -> look -> do -> log out over a live socket (its own
# isolated port + temp DB, timed). We prove the acceptance path GREEN before inviting
# a human in. The round-trip timing is banked as performance evidence.
SMOKE_RESULT="skipped"
spark_line "Smoke -- proving the engine end-to-end (login · look · do · logout)..."
if make smoke >/tmp/ritual-smoke.log 2>&1; then
  SMOKE_RESULT="$(grep -Eo '[0-9]+/[0-9]+ steps passed.*round-trips' /tmp/ritual-smoke.log | tail -1)"
  ok "End-to-end smoke passed${SMOKE_RESULT:+ ($SMOKE_RESULT)}."
else
  printf '%b' "$DIM"; tail -20 /tmp/ritual-smoke.log; printf '%b' "$OFF"
  die "The end-to-end smoke failed -- the engine is not ready. Fix it, then start the ritual again."
fi

# --- Bank the after-action record (dated evidence; reports/* is git-ignored) --
# Written once all gates are green, before the forge lights -- so the record exists
# even if you leave at the login prompt. Traceable to the commit that produced it.
RITUAL_REPORTS="reports/ritual"
mkdir -p "$RITUAL_REPORTS"
REPORT_FILE="$RITUAL_REPORTS/$(date -u +%Y-%m-%d).md"
{
  echo "## Ritual START $(date -u +%Y-%m-%dT%H:%M:%SZ)  ($(git rev-parse --short HEAD 2>/dev/null || echo '?'))"
  echo "- seed: \`$SEED\`"
  echo "- IGNITION: gates green - ${IGN_TESTS:-tests passed}; coverage ${IGN_COV:-ok}"
  echo "- WARDS: SAST clean · secrets clean · deps ${WARDS_AUDIT:-clean}"
  echo "- READINESS: registry validates"
  echo "- VERITAS: all claims verified (truth check)"
  echo "- INTEGRITY: ${INTEGRITY_STATUS:-filed}"
  echo "- SMOKE: ${SMOKE_RESULT:-passed}"
  echo "- MIRROR: ${BRANCH:-?} - ${MIRROR_STATUS:-unknown}"
  echo ""
} >> "$REPORT_FILE"
ok "After-action record banked: $REPORT_FILE"

# Is something already listening on :$PORT? Prefer `ss` (no connection made);
# fall back to a single, harmless connect only if ss is unavailable. We avoid
# connecting in a loop -- each connect spawns a real gateway session.
forge_is_up() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | grep -q ":$PORT[[:space:]]" && return 0 || return 1
  fi
  (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && { exec 3>&- 2>/dev/null; return 0; }
  return 1
}

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

# --- 7. THE FORGE: light the gateway ---------------------------------------
spark_line "The Forge -- lighting the gateway on :$PORT..."
if forge_is_up; then
  ok "A forge is already burning on :$PORT -- joining it (won't disturb it on exit)."
else
  : >/tmp/ritual-spark.log
  # PYTHONUNBUFFERED so the gateway's "listening" line hits the log immediately
  # -- we wait on that line instead of connecting (a connect would spawn a real
  # session on the very server we're booting).
  PYTHONUNBUFFERED=1 FORGE_SEED="$SEED" spark >/tmp/ritual-spark.log 2>&1 &
  FORGE_PID=$!
  STARTED_HERE=1
  for _ in $(seq 1 60); do
    if grep -q "listening on" /tmp/ritual-spark.log 2>/dev/null; then break; fi
    if ! kill -0 "$FORGE_PID" 2>/dev/null; then
      printf '%b' "$DIM"; cat /tmp/ritual-spark.log; printf '%b' "$OFF"
      die "The forge failed to light (see above)."
    fi
    sleep 0.25
  done
  grep -q "listening on" /tmp/ritual-spark.log || die "The forge did not announce itself in time."
  ok "The forge is lit (pid $FORGE_PID) -- '$SEED' is live on :$PORT."
fi

# --- 8. THE GATE: open the MUD window --------------------------------------
spark_line "The Gate -- opening the MUD window (log in at the front desk)..."
printf '%b   Character (character@account) or NEW awaits. Ctrl-C or QUIT to leave.%b\n\n' "$DIM" "$OFF"
sleep 0.4
# Prefer our own client: it honours the password blackout with only the stdlib,
# so secrets stay hidden even where `telnet` isn't installed. `nc` cannot mask a
# password (it ignores telnet negotiation) -- it's the last resort, and loud.
if [ -f "$ROOT/scripts/mud_client.py" ]; then
  python3 "$ROOT/scripts/mud_client.py" 127.0.0.1 "$PORT"
elif command -v telnet >/dev/null 2>&1; then
  telnet 127.0.0.1 "$PORT"
elif command -v nc >/dev/null 2>&1; then
  warn "Falling back to nc -- your PASSWORD WILL BE VISIBLE (nc can't mask it)."
  warn "Prefer scripts/mud_client.py or telnet/Mudlet to keep it hidden. See docs/RUNNING.md."
  nc 127.0.0.1 "$PORT"
else
  warn "No client found. The forge is lit on :$PORT -- connect with Mudlet."
  warn "Press Ctrl-C here to end the ritual and bank the forge."
  while [ "$STARTED_HERE" = "1" ] && kill -0 "${FORGE_PID:-0}" 2>/dev/null; do sleep 1; done
fi
